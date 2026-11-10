"""Manual human action in the LOCAL TEST DOUBLE. Not a production approval UI."""
import argparse
import json
import urllib.request

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('action', choices=['snapshot','approve'])
parser.add_argument('--version',type=int)
args=parser.parse_args()
base='http://127.0.0.1:8094'
headers={'X-Fixture-Actor':'fixture-coordinator','Content-Type':'application/json'}
if args.action=='approve':
    if not args.version: parser.error('--version is required')
    confirmation=input(f'LOCAL FIXTURE: type APPROVE {args.version} to confirm this human decision: ')
    if confirmation != f'APPROVE {args.version}': raise SystemExit('No approval submitted.')
    body=json.dumps({'version':args.version,'human_confirmed':True}).encode()
    req=urllib.request.Request(base+'/fixture/control/approve',data=body,headers=headers)
else:
    req=urllib.request.Request(base+'/fixture/v1/snapshot',headers=headers)
with urllib.request.urlopen(req,timeout=5) as response:
    result=json.load(response)
# Avoid printing lease tokens or raw report text in a routine state check.
if args.action=='snapshot':
    result={k:result[k] for k in ['fixture','phase','version','revision','pending_plan','resources','assignments','approvals','deliveries','failures','audit']}
print(json.dumps(result,indent=2,ensure_ascii=False))
