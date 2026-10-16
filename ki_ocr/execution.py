"""Full A+B page loop ported from the actual formal LANCZOS R6 worker.
No managed resource admission is replaced here. The caller admits and drains.
"""
import copy,hashlib,json,time
from pathlib import Path
from .pipeline import ROOT,bind,read,sha
from .tele_canonical import plain

def save(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp')
 tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8');tmp.replace(p)

def run_with_admitted_client(prepared_path, client, output, deadline, draining=lambda:False, expected_prepared_sha=None):
    """Real render/layout/selection/generation/assembly; original owner supplies client and deadline."""
    assert expected_prepared_sha is not None and sha(prepared_path)==expected_prepared_sha,'PREPARED_MANIFEST_SHA_REQUIRED'
    prepared=read(prepared_path)
    for name,digest in prepared['entry_code_pins'].items():
        assert sha(ROOT/name)==digest,'PREPARED_CODE_BYTES_CHANGED'
    assert sha(prepared['config_path'])==prepared['config_SHA256']
    assert sha(prepared['binding_path'])==prepared['binding_SHA256']
    b,cfg=bind(prepared['binding_path']);full=cfg;MODEL=Path(b['model'])
    import TeleOCR.config as config
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    c={'warmup_schedule':[],'schedule':prepared['schedule']}
    state={'status':'RUNNING','completed':[],'warmup_completed':[],'source_N':prepared['source_N'],
           'page_arm_N':prepared['page_arm_N'],'GT_reads':0,'prediction_body_exported':False,
           'shared_initialization_seconds':None,'model_engine_load_seconds':None,
           'model_load_accounting':'owner inclusive attempt accounting required'}
    init_start=time.monotonic()
    import torch
    torch.set_num_threads(1)
    assert torch.cuda.device_count() == 1
    llm = client.client.vllm_llm
    params = copy.deepcopy(client.sampling_params)
    params['table'].presence_penalty = 0.
    params['table'].frequency_penalty = 0.
    client.sampling_params = params
    client.helper.sampling_params = params
    assert client.prompts == cfg['engine']['expected_prompts']
    old = cfg['complete_requested_native_vllm_sampling']
    current = {k:plain(client.client.build_vllm_sampling_params(v)) for k,v in params.items()}
    assert current == old,'FULL_ACTUAL_SAMPLING_PARAMS_CHANGED'
    from . import menu as core, glyph_est5 as meter, best_effort as selector
    from context_runtime import bind_fresh_engine
    from telemetry import Journal
    gates = []
    journal = Journal(out,full,client.prompts['table'])
    def note(g):
        gates.append(dict(g))
        journal.note_context(g)
    bind_fresh_engine(llm,cfg['engine'],read(MODEL/'config.json'),note,
                      lambda v:save(out/'ACTUAL_ENGINE_CACHE_POLICY.json',v))
    journal.bind(llm)
    from . import native_sourcecap as cap
    cap.install()
    from PIL import Image,ImageOps
    import numpy as np
    from transformers import AutoProcessor
    from TeleOCR.tools.read_file import read_fn
    from TeleOCR.tools.pdf_image_tools import convert_pdf_bytes_to_bytes,load_images_from_pdf
    from TeleOCR.tools.enum_class import ImageType
    from TeleOCR.src.model_output_to_middle_json import result_to_middle_json
    from TeleOCR.src.vlm_middle_json_mkcontent import union_make
    from TeleOCR.data_reader_writer import ImageDataWriter
    import pypdfium2
    proc = AutoProcessor.from_pretrained(MODEL,local_files_only=True,use_fast=True)
    state['shared_initialization_seconds'] = time.monotonic()-init_start
    state['status'] = 'RUNNING'
    save(out/'RESULT_NUMERIC.json',state)
    source = prepared
    chatcache = {}

    def measured_candidate(image,prompt,scale):
        if prompt not in chatcache:
            chatcache[prompt] = proc.tokenizer.apply_chat_template(client.client.build_messages(prompt),tokenize=False,add_generation_prompt=True)
        captured=[];ip=proc.image_processor;original=ip.resize
        def tap(*a,**kw):
            y=original(*a,**kw);captured.append(y.detach().cpu());return y
        ip.resize=tap
        try:batch=proc(images=[image],text=[chatcache[prompt]],return_tensors='pt')
        finally:ip.resize=original
        assert len(captured)==1
        arr=captured[0].numpy();arr=np.moveaxis(arr,-3,-1).reshape(-1,arr.shape[-2],arr.shape[-1],3)[0]
        actual=Image.fromarray(arr)
        h,support=meter.estimate(actual,q=75)
        grid=batch['image_grid_thw'][0].tolist();P_len=len(batch['input_ids'][0])
        return dict(id='s'+str(scale),scale=scale,h=h,support=support,
                    P=P_len,V=int(np.prod(grid))//4,context=32768,reserve=8192,
                    resource_admitted=P_len+8192<=32768)

    def resize(image,scale):
        return image if scale==1 else image.resize(tuple(max(1,round(v*scale)) for v in image.size),Image.Resampling.LANCZOS)

    for slot in c['warmup_schedule'] + c['schedule']:
        warming = slot['slot'] < 0
        if draining() or time.time() >= deadline-20:
            state['status']='DRAINED_BEFORE_NEXT_PAGE_ARM';break
        page = source['rows'][slot['page_index']]
        arm = slot['arm']
        telemetry_id = page['page_id']+'__'+arm+('__WARMUP' if warming else '')
        journal.begin_page({'original_id':telemetry_id,'index':slot['slot']})
        assert journal.row['original_id']==telemetry_id and journal.row['index']==slot['slot']
        start=time.monotonic();ph={};packet=None;doc=None
        try:
            t=time.monotonic();path=Path(page['input_path'])
            assert sha(path)==page['encoded_SHA256']
            with Image.open(path) as original_image:
                wh=list(ImageOps.exif_transpose(original_image).size)
            assert wh==page['original_WH']
            pdf=convert_pdf_bytes_to_bytes(read_fn(path))
            with cap.raster_source(None if arm=='OFFICIAL_ORIGINAL' else wh):
                frames,doc=load_images_from_pdf(pdf,image_type=ImageType.PIL,threads=config.PDF_TOOLS_WORKER_MAX_NUM)
            assert len(frames)==1
            image=frames[0]['img_pil']
            ph['source_read_PDF_convert_200DPI_render_seconds']=time.monotonic()-t
            t=time.monotonic();layout_raw_before=journal.raw_count;layout_gates_before=len(gates)
            blocks=client.layout_detect(image)
            assert journal.raw_count-layout_raw_before==1 and len(gates)-layout_gates_before==1 and not journal.errors,'LAYOUT_RAW_GATE_METADATA_CARDINALITY'
            ph['fresh_layout_seconds']=time.monotonic()-t
            t=time.monotonic();source_crops=[];helper=client.helper;prior_resize=helper.resize_by_need
            def tap(crop):
                source_crops.append(crop.copy());return prior_resize(crop)
            helper.resize_by_need=tap
            try:images,prompts,sp,indices=helper.prepare_for_extract(image,blocks)
            finally:helper.resize_by_need=prior_resize
            assert len(images)==len(prompts)==len(sp)==len(indices)==len(source_crops)
            ph['native_crop_and_prepare_seconds']=time.monotonic()-t
            t=time.monotonic();selected=[];reason_counts={};candidate_records=0;processor_calls=0;roi_meta=[]
            if arm=='OFFICIAL_ORIGINAL':
                selected=images
            else:
                for native,source_crop,prompt,idx in zip(images,source_crops,prompts,indices):
                    oh,osupport=meter.estimate(source_crop,q=75)
                    base=measured_candidate(native,prompt,1);processor_calls+=1
                    supported=prompt in (client.prompts['text'],client.prompts['table'])
                    protected=blocks[idx].type in ('equation','equation_block','formula','algorithm') or not supported
                    scales=core.gf_menu_scales(base,oh,osupport,supported,protected)
                    candidates=[base]
                    for scale in scales:
                        if scale==1:continue
                        candidates.append(measured_candidate(resize(native,scale),prompt,scale));processor_calls+=1
                    candidate_records+=len(candidates)
                    choice=selector.select(candidates,T=12 if prompt==client.prompts['text'] else 11,
                                           L=11,max_scale=2,supported_domain=supported,protected=protected,
                                           original_h=oh,original_support=osupport)
                    reason_counts[choice['reason']]=reason_counts.get(choice['reason'],0)+1
                    chosen=next(v for v in candidates if v['id']==choice['selected_id'])
                    assert chosen['resource_admitted']
                    roi_meta.append({'roi_index':idx,'prompt_profile':'text' if prompt==client.prompts['text'] else ('table' if prompt==client.prompts['table'] else 'other'),
                                     'block_type':str(blocks[idx].type),'supported':supported,'protected':protected,
                                     'original_h':oh,'original_support':osupport,
                                     'native_h':base['h'],'native_support':base['support'],'native_V':base['V'],
                                     'selected_h':chosen['h'],'selected_support':chosen['support'],'selected_V':chosen['V'],
                                     'selected_scale':choice['selected_scale'],'B_triggered':bool(choice.get('triggered',False)),
                                     'B_changed_scale':choice['selected_scale']!=1,'target_reached':bool(choice.get('target_reached',False)),
                                     'reason':choice['reason'],'candidate_N':len(candidates)})
                    selected.append(resize(native,choice['selected_scale']))
            ph['fresh_glyph_CPU_candidate_and_selection_seconds']=time.monotonic()-t
            t=time.monotonic();before=journal.raw_count;gate_before=len(gates)
            outputs=client.client.batch_predict(selected,prompts,sp)
            assert len(outputs)==len(indices) and journal.raw_count-before==len(indices) and len(gates)-gate_before==len(indices) and not journal.errors,'CONTENT_OUTPUT_RAW_GATE_METADATA_CARDINALITY'
            ph['native_content_batch_seconds']=time.monotonic()-t
            t=time.monotonic();result_blocks=copy.deepcopy(blocks)
            for idx,text in zip(indices,outputs):
                assert isinstance(text,str)
                result_blocks[idx].content=text
            result_blocks=helper.post_process(result_blocks)
            dest=out/('private_warmup_predictions' if warming else 'private_predictions')/f"page{page['index']}"/arm
            writer=ImageDataWriter(str(out/'markdown'/arm/'images'/page['page_id']))
            doc2=pypdfium2.PdfDocument(pdf)
            try:middle=result_to_middle_json([result_blocks],frames,doc2,writer)
            finally:doc2.close()
            markdown=union_make(middle['pdf_info'],'images/'+page['page_id'])
            writer.save_all_images();dest.mkdir(parents=True,exist_ok=True)
            (dest/'prediction.md').write_text(markdown,encoding='utf-8')
            (dest/'middle.json').write_text(json.dumps(middle),encoding='utf-8')
            (out/'markdown'/arm/(page['page_id']+'.md')).write_text(markdown,encoding='utf-8')
            ph['native_postprocess_and_assembly_write_seconds']=time.monotonic()-t
            e2e=time.monotonic()-start
            state['warmup_completed' if warming else 'completed'].append({'slot':slot,'page_id':page['page_id'],'arm':arm,
                    'E2E_seconds':e2e,'phases':ph,'fresh_layout_calls':1,'ROI_N':len(indices),
                    'fresh_candidate_N':candidate_records,'actual_processor_calls':processor_calls,
                    'B_triggered_N':sum(v['B_triggered'] for v in roi_meta),
                    'B_changed_scale_N':sum(v['B_changed_scale'] for v in roi_meta),
                    'native_V_sum':sum(v['native_V'] for v in roi_meta) if arm=='GLYPHFIT_FULL' else None,
                    'selected_V_sum':sum(v['selected_V'] for v in roi_meta) if arm=='GLYPHFIT_FULL' else None,
                    'ROI_numeric_metadata':roi_meta,
                    'choice_reason_counts':reason_counts,'prediction_SHA256':sha(dest/'prediction.md'),
                    'prediction_private_path':str(dest/'prediction.md')})
            save(out/'RESULT_NUMERIC.json',state)
        except BaseException as err:
            state['status']='FAILED_RETAIN_COMPLETED';state['error_type']=type(err).__name__
            state['failed_slot']=slot;state['failed_elapsed_seconds']=time.monotonic()-start
            save(out/'RESULT_NUMERIC.json',state)
            raise
        finally:
            if doc is not None:doc.close()
    if len(state['completed'])==prepared['page_arm_N'] and len(state['warmup_completed'])==0:state['status']='COMPLETE_FROZEN_AB_ALL_PAGE_ARMS'
    save(out/'RESULT_NUMERIC.json',state)
    print(json.dumps({'status':state['status'],'warmup_completed_N':len(state['warmup_completed']),'completed_N':len(state['completed']),
                      'E2E_by_arm':{arm:[x['E2E_seconds'] for x in state['completed'] if x['arm']==arm]
                                    for arm in ('OFFICIAL_ORIGINAL','GLYPHFIT_FULL')},
                      'shared_initialization_seconds':state['shared_initialization_seconds'],
                      'result_path':str(out/'RESULT_NUMERIC.json')}))
    return state
