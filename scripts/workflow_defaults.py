"""Clean packaged workflow canvases without changing their execution graphs."""
from pathlib import Path
import json
from workflow_panels import fold_into_panel
from workflow_seeds import apply_seed_defaults
# Notes have no execution effect. Fixed model/configuration and plumbing nodes live inside
# a subgraph; user inputs, tuning controls and previews stay on the main canvas.
internal={'UNETLoader','CLIPLoader','VAELoader','CheckpointLoaderSimple','ModelSamplingAuraFlow','CFGNorm',
'VAEDecode','VAEEncode','GetImageSize','ComfyMathExpression','ImageScale','EmptySD3LatentImage',
'GetNode','SetNode','EmptyFlux2LatentImage','Flux3LayoutPrompt','ReferenceMultiLatent','BatchImagesNode','ConditioningZeroOut'}
def normalize(repo):
 changed=0
 for p in repo.glob('versions/*/workflows/*.json'):
  d=json.loads(p.read_text()); before=json.dumps(d)
  for graph in [d]+d.get('definitions',{}).get('subgraphs',[]):
   graph['nodes']=[n for n in graph.get('nodes',[]) if n['type'] not in {'Note','MarkdownNote'}]
  apply_seed_defaults(d)
  hide={n['id'] for n in d['nodes'] if n.get('title') != 'Model internals' and (n['type'] in internal or (not n.get('widgets_values') and not any(i.get('widget') for i in n.get('inputs',[])) and not n['type'].startswith(('Save','Preview','Load')) and n['type'] not in {'ImageCompare','CreateBoundingBoxes'}))}
  # All Set/Get nodes move together so named connections retain their scope.
  if hide:
   fold_into_panel(d,'Model internals', {n['id'] for n in d['nodes']} - hide, [])
   panel=d['nodes'][-1];panel['flags']['collapsed']=True
  # Rebuild output back-references after boundary links have been replaced by the fold.
  for graph in [d]+d.get('definitions',{}).get('subgraphs',[]):
   outgoing={}
   for link in graph.get('links',[]):
    if isinstance(link,dict):lid,source,slot=link['id'],link['origin_id'],link['origin_slot']
    else:lid,source,slot=link[:3]
    outgoing.setdefault((source,slot),[]).append(lid)
   for node in graph['nodes']:
    for slot,output in enumerate(node.get('outputs',[])):
     output['links']=outgoing.get((node['id'],slot),[]) or None
  if json.dumps(d)!=before:
   p.write_text(json.dumps(d,indent=2)+'\n'); changed+=1
 print(repo.name,changed,'workflows cleaned')

if __name__ == "__main__":
 normalize(Path(__file__).resolve().parents[1])
