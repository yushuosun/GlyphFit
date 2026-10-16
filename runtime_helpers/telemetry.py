"""Observational raw journal; no sampling, image, or model request mutation."""
from pathlib import Path
import json,hashlib,os,time,copy
def plain(x):
 if isinstance(x,(str,int,float,bool,type(None))):return x
 if isinstance(x,dict):return {str(k):plain(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [plain(v) for v in x]
 if isinstance(x,set):return sorted(plain(v) for v in x)
 if hasattr(x,'__struct_fields__'):return {k:plain(getattr(x,k)) for k in x.__struct_fields__}
 return str(x)
class Journal:
 def __init__(self,stage,contract,table_prompt):
  self.stage=Path(stage);self.contract=contract;self.table_prompt=table_prompt;self.row=None;self.call=0;self.raw_count=0;self.errors=[];self.worker_SHA256=hashlib.sha256((self.stage/'replay_worker.py').read_bytes()).hexdigest() if (self.stage/'replay_worker.py').exists() else None
 def append(self,name,value):
  with (self.stage/name).open('a',encoding='utf-8') as f:f.write(json.dumps(value,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
 def failure(self,where,error):
  self.errors.append({'where':where,'error':type(error).__name__+':'+str(error),'epoch':time.time(),'page':None if self.row is None else self.row['original_id']})
  try:self.append('TELEMETRY_ERRORS.jsonl',self.errors[-1])
  except Exception:pass
 def begin_page(self,row):self.row=row
 def note_context(self,v):
  try:self.append('CONTEXT_BUDGETS.jsonl',dict(v,page_id=None if self.row is None else self.row['original_id'],generation_call=self.call))
  except Exception as e:self.failure('context_record',e)
 def bind(self,llm):
  original=llm.generate
  def observed(*args,**kwargs):
   self.call+=1;call=self.call;records=[];started=time.time();prompts=kwargs.get('prompts',args[0] if args else []);sps=kwargs.get('sampling_params',args[1] if len(args)>1 else None)
   try:
    for i,prompt in enumerate(prompts):
     image=prompt['multi_modal_data']['image'];sp=sps[i] if isinstance(sps,(list,tuple)) else sps;chat=prompt['prompt'];kind='table' if self.table_prompt in chat else 'other'
     rgb=image.convert('RGB');rgbsha=hashlib.sha256(rgb.tobytes()).hexdigest();crop=None
     if kind=='table':
      root=self.stage/'consumer_table_images'/str(self.row['index']);root.mkdir(parents=True,exist_ok=True);crop=root/('call_%06d_image_%03d.png'%(call,i));temporary=crop.with_suffix('.tmp');rgb.save(temporary,format='PNG');os.replace(temporary,crop)
     key={'full_requested_sampling_params':plain(sp),'chat_prompt_SHA256':hashlib.sha256(chat.encode()).hexdigest(),'actual_RGB_SHA256':rgbsha,'actual_WH':list(rgb.size),'model_weight_SHA256':self.contract['model_weight_SHA256'],'model_config_pins':self.contract['model_config_pins'],'consumer_code_pins':self.contract['consumer_code_pins'],'context_contract_SHA256':self.contract['context_contract_SHA256']}
     records.append({'producer_worker_SHA256':self.worker_SHA256,'telemetry_SHA256':self.contract['telemetry_SHA256'],'page_id':self.row['original_id'],'full_input_index':self.row['index'],'generation_call':call,'batch_image_index':i,'request_kind':kind,'actual_table_crop_path':None if crop is None else str(crop),'cache_contract':key,'cache_key_SHA256':hashlib.sha256(json.dumps(key,sort_keys=True).encode()).hexdigest()})
    self.append('REQUEST_BATCHES.jsonl',{'status':'DISPATCHED','page_id':self.row['original_id'],'call':call,'requests':len(prompts),'epoch':started})
   except Exception as error:self.failure('pre_request_metadata',error)
   outputs=original(*args,**kwargs)
   try:
    assert len(records)==len(outputs),'METADATA_REQUEST_COUNT'
    # One fsynced batch contains complete ordered bytes, then the commit marker.
    returned=[]
    for record,out in zip(records,outputs):
     choice=out.outputs[0];record.update(raw_text=choice.text,token_ids=[int(x) for x in choice.token_ids],prompt_token_ids=[int(x) for x in (out.prompt_token_ids or [])],prompt_tokens=len(out.prompt_token_ids or []),output_tokens=len(choice.token_ids),finished=bool(out.finished),finish_reason=choice.finish_reason,stop_reason=plain(choice.stop_reason),elapsed_batch_seconds=time.time()-started,request_id=str(out.request_id),long_table_output=record['request_kind']=='table' and (len(choice.token_ids)>=8192 or choice.finish_reason=='length'))
     returned.append(record)
    self.append('RAW_BATCH_OUTPUTS.jsonl',{'page_id':self.row['original_id'],'generation_call':call,'status':'COMMITTED','outputs':returned});self.raw_count+=len(returned)
    self.append('REQUEST_BATCHES.jsonl',{'status':'COMMITTED','page_id':self.row['original_id'],'call':call,'requests':len(returned),'epoch':time.time()})
   except Exception as error:self.failure('post_request_metadata',error)
   return outputs
  llm.generate=observed
  return self
