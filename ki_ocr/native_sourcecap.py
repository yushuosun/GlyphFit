"""Scoped native renderer patch; preserve native JPEG/PDF and postprocessing."""
import contextlib,hashlib,inspect,json,math,multiprocessing,os
from pathlib import Path
SOURCE_RASTER_WH=None
AUDIT_PATH=None
def capped_scale(page,default_scale):
 if SOURCE_RASTER_WH is None:return default_scale
 pw,ph=page.get_size();sw,sh=SOURCE_RASTER_WH
 return min(default_scale,sw/pw,sh/ph)
def install():
 import TeleOCR.tools.pdf_reader as reader
 import TeleOCR.tools.pdf_image_tools_pdfium as pdfium_tools
 original=reader.page_to_image
 source=inspect.getsource(original)
 assert hashlib.sha256(Path(reader.__file__).read_bytes()).hexdigest()=='4094bf09b5af96acc32c38f2d4de9480709b857f828c1530c9e8428fab5d75ef'
 needle='    bitmap: PdfBitmap = page.render(scale=scale)'
 assert source.count(needle)==1
 patched=source.replace(needle,'    scale = _sourcecap_scale(page, scale)\n'+needle)
 namespace=dict(original.__globals__,_sourcecap_scale=capped_scale)
 exec(compile(patched,reader.__file__+':raster_sourcecap','exec'),namespace)
 native_capped=namespace['page_to_image']
 def audited(page,dpi=200,max_width_or_height=3500):
  pw,ph=page.get_size();default=min(dpi/72,max_width_or_height/max(pw,ph))
  im,scale=native_capped(page,dpi,max_width_or_height)
  if SOURCE_RASTER_WH is not None:
   assert im.width<=SOURCE_RASTER_WH[0] and im.height<=SOURCE_RASTER_WH[1],'ACTUAL_CAP_EXCEEDS_SOURCE_NO_POSTRESIZE'
  if AUDIT_PATH:
   event={'source_WH':SOURCE_RASTER_WH,'page_point_WH':[pw,ph],'default_WH':[math.ceil(pw*default),math.ceil(ph*default)],'default_WH_origin':'DERIVED_EXACT_PDFIUM_CEIL_RULE','capped_WH':list(im.size),'capped_WH_origin':'ACTUAL_NATIVE_PDFIUM_RENDER','default_scale':default,'capped_scale':scale,'PID':os.getpid(),'raster_cap_applied':SOURCE_RASTER_WH is not None,'render_RGB_SHA256':hashlib.sha256(im.convert('RGB').tobytes()).hexdigest()}
   with Path(AUDIT_PATH).open('a') as stream:stream.write(json.dumps(event)+'\n')
  return im,scale
 reader.page_to_image=audited;pdfium_tools.page_to_image=audited
 return {'original_source':source,'patched_source':patched,'multiprocessing_start_method':multiprocessing.get_start_method()}
@contextlib.contextmanager
def raster_source(source_wh,audit_path=None):
 global SOURCE_RASTER_WH,AUDIT_PATH
 old=SOURCE_RASTER_WH,AUDIT_PATH
 SOURCE_RASTER_WH=tuple(source_wh) if source_wh is not None else None;AUDIT_PATH=audit_path
 try:
  # Native PDFium ProcessPool children inherit this one-page source bound under
  # Linux fork. Do not silently change production worker/resource guards.
  assert multiprocessing.get_start_method()=='fork','NATIVE_RENDER_CONTEXT_NOT_INHERITED'
  yield
 finally:SOURCE_RASTER_WH,AUDIT_PATH=old

