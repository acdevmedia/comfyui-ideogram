"""Create or update the matching Runpod template, preserving a single account listing."""
import argparse,json,os,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--dry-run',action='store_true');args=parser.parse_args()
 p=json.loads((ROOT/'config/runpod-template.json').read_text());p['readme']=(ROOT/'README.md').read_text()
 if args.dry_run:print(json.dumps(p,indent=2));return
 values={}
 if (ROOT/'.env').exists():
  for line in (ROOT/'.env').read_text().splitlines():
   if '=' in line and not line.lstrip().startswith('#'):
    k,v=line.split('=',1);values[k.strip()]=v.strip().strip('\"\x27')
 key=os.getenv('RUNPOD_API_KEY') or values.get('RUNPOD_API_KEY');assert key,'RUNPOD_API_KEY is required'
 def request(url,data=None):
  req=urllib.request.Request(url,data=json.dumps(data).encode() if data is not None else None,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=45) as response:return json.load(response)
 recorded=ROOT/'.runpod/template-source.json'
 known=json.loads(recorded.read_text())['templateId'] if recorded.exists() else None
 templates=request('https://rest.runpod.io/v1/templates')
 matches=[t for t in templates if t['id']==known] or [t for t in templates if t['name']==p['name']]
 assert len(matches)<=1,'Duplicate account templates; resolve before updating'
 value={'name':p['name'],'imageName':p['imageName'],'containerDiskInGb':p['containerDiskInGb'],'volumeInGb':0,'volumeMountPath':'/workspace','isPublic':p['isPublic'],'isServerless':False,'dockerArgs':'','ports':','.join(p['ports']),'portsConfig':[{'port':x.split('/')[0],'name':'ComfyUI'} for x in p['ports']],'env':[{'key':k,'value':v} for k,v in p['env'].items()],'readme':p['readme'],'category':'NVIDIA','startJupyter':False,'startSsh':False}
 if matches:value['id']=matches[0]['id']
 result=request('https://api.runpod.io/graphql',{'query':'mutation($input: SaveTemplateInput!) { saveTemplate(input:$input) { id name imageName } }','variables':{'input':value}})
 if result.get('errors'):raise RuntimeError([e['message'][-200:] for e in result['errors']])
 print(json.dumps(result['data']['saveTemplate'],indent=2))
if __name__=='__main__':main()
