"""Frozen A+B runtime binding and CPU prepare. GT is outside this module.

The full page-arm execution function is generated from the actual R6 worker
in execution.py. Managed deployments call it inside their original owner guard.
"""
import argparse
import copy
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

from .tele_canonical import plain
from ._resources import read_binding, resource_path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = resource_path('configs/ki_ocr_ab.json')
ARMS = ('OFFICIAL_ORIGINAL', 'GLYPHFIT_FULL')

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def save_new(p, data):
    with Path(p).open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write('\n')

def bind(binding):
    """Bind existing local dependencies by bytes; never download or install."""
    b = read_binding(binding)
    if set(b) != {'source', 'model', 'runtime_helpers', 'execution_policy'}:
        raise ValueError('Exactly source/model/runtime_helpers/execution_policy are required')
    if b['execution_policy'] not in ('managed', 'standalone'):
        raise ValueError('Unknown execution policy')
    cfg = read(CONFIG)
    for root_key, pins in [('source', cfg['consumer_code_pins']), ('model', cfg['model_config_pins']),
                           ('model', cfg['processor_asset_pins']),
                           ('runtime_helpers', cfg['private_runtime_pins'])]:
        for name, digest in pins.items():
            if sha(Path(b[root_key]) / name) != digest:
                raise ValueError('Frozen dependency bytes differ: ' + root_key + '/' + name)
    sys.path[:0] = [str(Path(b['runtime_helpers']).resolve()), str(Path(b['source']).resolve())]
    return b, cfg

def load_dependencies(binding):
    b, cfg = bind(binding)
    import torch
    import cv2
    import numpy as np
    import pypdfium2
    from PIL import Image
    from transformers import AutoProcessor
    from vllm import SamplingParams
    from TeleOCR.vlm_utils.TeleOCR_model import TeleOCRMODEL_SERVICE
    from TeleOCR.vlm_utils.TeleOCR_client import DEFAULT_SAMPLING_PARAMS, DEFAULT_PROMPTS, TeleOCRClientHelper
    from TeleOCR.vlm_utils.vlm_client.vllm_engine_client import VllmEngineVlmClient
    from TeleOCR.vlm_utils.vlm_client.base_client import VlmClient
    from TeleOCR.tools.read_file import read_fn
    from TeleOCR.tools.pdf_image_tools import convert_pdf_bytes_to_bytes, load_images_from_pdf
    from TeleOCR.tools.enum_class import ImageType
    from TeleOCR.src.model_output_to_middle_json import result_to_middle_json
    from TeleOCR.src.vlm_middle_json_mkcontent import union_make
    from TeleOCR.data_reader_writer import ImageDataWriter
    from context_runtime import bind_fresh_engine
    from telemetry import Journal
    from . import menu, glyph_est5, best_effort, native_sourcecap
    versions = {name: importlib.metadata.version(name) for name in
                ('torch', 'transformers', 'vllm', 'Pillow', 'numpy', 'torchvision', 'pypdfium2', 'tokenizers')}
    versions['torch_build'] = torch.__version__
    versions['opencv'] = cv2.__version__
    # Processor behavior additionally has tensor equivalence checks, not just version labels.
    for name, version in cfg['processor_runtime_versions'].items():
        if versions[name] != version:
            raise ValueError('Frozen runtime version differs: ' + name)
    backend = VllmEngineVlmClient.__new__(VllmEngineVlmClient)
    VlmClient.__init__(backend)
    backend.model_max_length = 32768
    backend.VllmSamplingParams = SamplingParams
    backend.debug = False
    params = copy.deepcopy(DEFAULT_SAMPLING_PARAMS)
    params['table'].presence_penalty = 0.
    params['table'].frequency_penalty = 0.
    actual = {k: plain(backend.build_vllm_sampling_params(v)) for k, v in params.items()}
    if actual != cfg['complete_requested_native_vllm_sampling'] or DEFAULT_PROMPTS != cfg['engine']['expected_prompts']:
        raise ValueError('Complete real GEN or prompts differ')
    proc = AutoProcessor.from_pretrained(b['model'], local_files_only=True, use_fast=True)
    return b, cfg, proc, backend, versions

def prepare(binding, inputs, output):
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise ValueError('CPU prepare requires CUDA_VISIBLE_DEVICES empty')
    b, cfg, proc, backend, versions = load_dependencies(binding)
    import torch
    from PIL import Image, ImageOps
    p = Path(inputs)
    files = sorted(p.iterdir()) if p.is_dir() else [p]
    files = [f for f in files if f.suffix.lower() in ('.png', '.jpg', '.jpeg')]
    if not files or len({f.stem for f in files}) != len(files):
        raise ValueError('No images or duplicate image stems')
    rows = []
    for i, f in enumerate(files):
        with Image.open(f) as image:
            wh = list(ImageOps.exif_transpose(image).size)
        rows.append({'index': i, 'page_id': f.stem, 'input_path': str(f.resolve()),
                     'encoded_SHA256': sha(f), 'original_WH': wh})
    result = {'schema': 'GLYPHFIT_AB_PREPARED_R2', 'status': 'CPU_PREPARED_BEFORE_WEIGHT_LOAD',
              'config_path': str(CONFIG.resolve()), 'config_SHA256': sha(CONFIG),
              'binding_path': str(Path(binding).resolve()), 'binding_SHA256': sha(binding),
              'entry_code_pins': {'ki_ocr/'+f.name: sha(f) for f in sorted((ROOT/'ki_ocr').glob('*.py'))},
              'rows': rows, 'source_N': len(rows), 'page_arm_N': len(rows)*2,
              'schedule': [{'slot': 2*i+j, 'page_index': i, 'arm': arm}
                           for i in range(len(rows)) for j, arm in enumerate(ARMS if i%2==0 else ARMS[::-1])],
              'runtime_versions': versions, 'baseline_GEN_equals_GlyphFit_GEN': True,
              'model_weight_loaded': False, 'GPU_initialized': torch.cuda.is_initialized(),
              'next_weight_load_call': 'TeleOCRMODEL_SERVICE.get_model(vllm-engine, model, None, **engine_kwargs)',
              'GT_reads': 0, 'score': None}
    if result['GPU_initialized']:
        raise ValueError('CPU preparation initialized CUDA')
    save_new(output, result)
    return result

def measure(proc, backend, meter, image, prompt, scale):
    """R6 actual processor tap, extended with full CPU identity hashes."""
    import numpy as np
    import torch
    from PIL import Image
    chat = proc.tokenizer.apply_chat_template(backend.build_messages(prompt), tokenize=False, add_generation_prompt=True)
    captured = []
    ip = proc.image_processor
    original = ip.resize
    def tap(*args, **kwargs):
        y = original(*args, **kwargs)
        captured.append(y.detach().cpu())
        return y
    ip.resize = tap
    try:
        batch = proc(images=[image], text=[chat], return_tensors='pt')
    finally:
        ip.resize = original
    if len(captured) != 1:
        raise ValueError('Expected one actual processor resize')
    arr = captured[0].numpy()
    arr = np.moveaxis(arr, -3, -1).reshape(-1, arr.shape[-2], arr.shape[-1], 3)[0]
    actual = Image.fromarray(arr)
    h, support = meter.estimate(actual, q=75)
    grid = batch['image_grid_thw'][0].tolist()
    ids = batch['input_ids'][0].tolist()
    pv = batch['pixel_values'].detach().contiguous().cpu()
    digest = lambda x: hashlib.sha256(x).hexdigest()
    return dict(id='s'+str(scale), scale=scale, h=h, support=support, grid=grid,
                P=len(ids), V=int(np.prod(grid))//4, context=32768, reserve=8192,
                resource_admitted=len(ids)+8192<=32768,
                candidate_RGB_SHA256=digest(image.convert('RGB').tobytes()), candidate_WH=list(image.size),
                actual_processor_RGB_SHA256=digest(actual.tobytes()), actual_processor_WH=list(actual.size),
                pixel_values_FP32_SHA256=digest(pv.numpy().tobytes()),
                pixel_values_BF16_SHA256=digest(pv.to(torch.bfloat16).contiguous().view(torch.uint8).numpy().tobytes()),
                expanded_input_ids_SHA256=digest(json.dumps(ids,separators=(',',':')).encode()),
                rendered_prompt_SHA256=digest(chat.encode()))

def create_client(binding):
    """Actual fixed model factory; call only inside original owner admission."""
    b, cfg = bind(binding)
    if sha(Path(b['model'])/'model.safetensors') != cfg['model_weight_SHA256']:
        raise ValueError('Model weight bytes differ')
    import TeleOCR.config as config
    config.BACKEND = 'vllm-engine'
    config.MAX_MODEL_LEN = 32768
    config.GPU_MEMORY_UTILIZATION = .5
    config.model_path = b['model']
    from TeleOCR.vlm_utils.TeleOCR_model import TeleOCRMODEL_SERVICE
    return TeleOCRMODEL_SERVICE.get_model('vllm-engine', config.model_path, None, **cfg['engine']['engine_kwargs'])

def validate_prepared(path, expected_sha):
    if sha(path) != expected_sha:
        raise ValueError('Prepared manifest bytes differ')
    prepared = read(path)
    if sha(prepared['config_path']) != prepared['config_SHA256'] or sha(prepared['binding_path']) != prepared['binding_SHA256']:
        raise ValueError('Prepared config or binding bytes differ')
    for name, digest in prepared['entry_code_pins'].items():
        if sha(ROOT/name) != digest:
            raise ValueError('Prepared entry code bytes differ: ' + name)
    bind(prepared['binding_path'])
    return prepared

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action', required=True)
    p = subs.add_parser('prepare')
    p.add_argument('--binding', required=True)
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    result = prepare(args.binding, args.input, args.output)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','schedule')}, indent=2))

if __name__ == '__main__':
    main()
