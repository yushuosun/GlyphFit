"""Actual frozen SWOCR A+B entry: CPU prepare or explicitly admitted inference."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

@contextlib.contextmanager
def standalone_admission(device, expected_uuid, output):
    """Private-machine CLI only. Managed runs retain their existing owner guard."""
    if sys.platform != 'linux':
        raise ValueError('Inference requires Linux fork')
    import fcntl
    def observe():
        line = subprocess.run(['nvidia-smi','-i',str(device),
            '--query-gpu=uuid,memory.used,utilization.gpu','--format=csv,noheader,nounits'],
            capture_output=True,text=True,timeout=15,check=True).stdout.strip().split(',')
        if len(line)!=3 or line[0].strip()!=expected_uuid or int(line[1])!=0 or int(line[2])!=0:
            raise ValueError('Explicit GPU identity or idle telemetry differs')
    observe()
    root = Path(output).resolve().parent/'standalone-device-locks'
    root.mkdir(exist_ok=True)
    with (root/(expected_uuid+'.lock')).open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        observe()
        os.environ['CUDA_VISIBLE_DEVICES']=str(device)
        yield

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('prepare');a.add_argument('--binding',required=True);a.add_argument('--input',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('run-standalone')
    a.add_argument('--prepared',required=True);a.add_argument('--prepared-sha',required=True)
    a.add_argument('--output',required=True);a.add_argument('--device',type=int,required=True);a.add_argument('--uuid',required=True)
    a.add_argument('--work-seconds',type=float,required=True)
    args=p.parse_args(argv)
    if args.action=='prepare':
        os.environ['CUDA_VISIBLE_DEVICES']=''
        from swocr.pipeline import prepare
        result=prepare(args.binding,args.input,args.output)
        summary={k:v for k,v in result.items() if k not in ('rows','schedule')}
        summary['prepared_manifest_SHA256']=hashlib.sha256(Path(args.output).read_bytes()).hexdigest()
        print(json.dumps(summary,indent=2));return
    # Read policy before any model/torch imports or GPU calls.
    from swocr.pipeline import read,sha
    if sha(args.prepared)!=args.prepared_sha:raise ValueError('Prepared manifest SHA differs')
    prepared=read(args.prepared)
    if read(prepared['binding_path'])['execution_policy']!='standalone':
        raise ValueError('Managed inference must call run_with_admitted_client inside the existing owner admission; this CLI cannot admit a cluster job')
    from swocr.pipeline import validate_prepared
    validate_prepared(args.prepared,args.prepared_sha)
    if args.work_seconds<=0:raise ValueError('Positive explicit work window required')
    from swocr.pipeline import create_client
    from swocr.execution import run_with_admitted_client
    with standalone_admission(args.device,args.uuid,args.output):
        start=time.time();client=create_client(prepared['binding_path'])
        result=run_with_admitted_client(args.prepared,client,args.output,start+args.work_seconds,
                                        expected_prepared_sha=args.prepared_sha)
    print(json.dumps({'status':result['status'],'completed_page_arm_N':len(result['completed']),
                      'inclusive_wall_seconds':time.time()-start,'score':None}))

if __name__=='__main__':main()
