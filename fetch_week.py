"""Experimental public-program importer. No personal data is read or sent."""
import datetime as dt,json,re,pathlib,sys
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
root='https://wol.jw.org/fi/wol/'
d=dt.date.fromisoformat(sys.argv[1]) if len(sys.argv)>1 else dt.datetime.now(ZoneInfo("Europe/Helsinki")).date()
d+=dt.timedelta(days=2-d.weekday()); y,w,_=d.isocalendar()
url=f'{root}meetings/r16/lp-fi/{y}/{w}'
def get(u):
 r=requests.get(u,timeout=30);r.raise_for_status();return BeautifulSoup(r.text,'html.parser')
s=get(url)
links=[a for a in s.select('a[href]') if re.search(r'/wol/d/r16/lp-fi/\d+',a['href']) and re.search(r'marraskuuta|joulukuuta|tammikuuta|helmikuuta|maaliskuuta|huhtikuuta|toukokuuta|kesäkuuta|heinäkuuta|elokuuta|syyskuuta|lokakuuta',a.get_text(' ',strip=True),re.I)]
from urllib.parse import urljoin
if not links: raise SystemExit('Viikon ohjelmalinkkiä ei tunnistettu; vanhaa aineistoa ei muutettu.')
source=urljoin(url,links[0]['href']);s=get(source);a=s.select_one('article') or s.select_one('#article');
if not a: raise SystemExit('Artikkelia ei löydy')
items=[]; section=''; pending=None
def add(title,min,kind='normal',ref='',summary='',url=''):
 items.append(dict(title=title,min=min,kind=kind,ref=ref,summary=summary,url=url))
# Extract short source headings only; no AI or invented summary.
summary_cache={}
def extract_points(article,ref):
 if not article:return []
 points=[]
 target=re.search(r'(?:kohta|kpl\.?|:)\s*(\d+)',ref,re.I)
 scope=article
 if target:
  for node in article.select('p,li'):
   if re.match(r'^'+target[1]+r'[.\s]',node.get_text(' ',strip=True)):
    scope=node;break
 for node in scope.select('strong,b,span.bold,span[class*="bold"]'):
  text=node.get_text(' ',strip=True)
  if 5<=len(text)<=150 and 2<=len(text.split())<=20 and text not in points:points.append(text)
  if len(points)==4:break
 return points
def feedback(href,ref):
 if not href:return ''
 key=(href,ref)
 if key not in summary_cache:
  try:
   page=get(href); article=page.select_one('article, #article, #articleContent')
   points=extract_points(article,ref)
   summary_cache[key]='\n'.join('• '+t for t in points) if points else ''
  except requests.RequestException as exc:
   print('Palautekoosteen haku epäonnistui:',href,exc)
   summary_cache[key]=''
 print('Palautekooste:',ref, 'OK' if summary_cache[key] else 'EI LÖYTYNYT',href)
 return summary_cache[key] or 'Tarkista tutkittava kohta lähdelinkistä ja lisää oma kooste.'
for e in a.select('h2,h3,p'):
 t=' '.join(e.stripped_strings)
 if e.name=='h2': section=t.upper()
 if e.name=='h3':
  m=re.search(r'Laulu\s+(\d+)',t,re.I)
  if m:
   if 'Loppusanat' in t:add('Loppusanat ja ilmoitukset',3,'closing')
   first=not items
   title='Laulu '+m[1]
   for link in e.select('a[href]'):
    if re.search(r'Laulu\s+'+m[1]+r'\b',link.get_text(' ',strip=True),re.I):
     try:
      page=get(urljoin(source,link['href']))
      heading=page.select_one('article h1, #article h1')
      if heading:
       name=heading.get_text(' ',strip=True)
       if name and not re.fullmatch(r'Laulu\s+\d+',name,re.I):title+=' – '+name
     except requests.RequestException:pass
     break
   add(title,3,'song')
   if 'rukous' in t.lower():
    add('Alkurukous' if first else 'Loppurukous',1,'prayer')
    if first:add('Alkusanat',1,'chair')
  elif re.match(r'\d+\.\s',t):pending=t
 elif e.name=='p' and pending:
  m=re.search(r'\((\d+)\s*min\)',t)
  if m:
   kind='student' if 'Raamatun lukeminen' in pending else 'study' if 'raamatuntutkistelu' in pending.lower() else 'normal'
   ref=''; href=''
   for l in e.select('a[href]'):
    z=l.get_text(' ',strip=True)
    if re.search(r'\b(?:th|lmd)\s*(?:osio|oppijakso)?\s*\d+',z,re.I):ref=z;href=urljoin(source,l['href']);break
   if 'VALMENNUSTA' in section and (ref or re.search(r'keskustel|kiinnost|opetus|puhe|raamatuntutkistelu',pending,re.I)):kind='student' if re.search(r'Puhe',pending) else 'pair'
   add(pending,int(m[1]),kind,ref,feedback(href,ref) if ref else '',href);pending=None
if len(items)<8 or not all(any(x['kind']==k for x in items) for k in ['closing','study','prayer']):raise SystemExit('Poikkeava ohjelma; tarkista käsin.')
label=next((e.get_text(' ',strip=True) for e in a.select('h2') if not any(k in e.get_text().upper() for k in ['AARTEITA','VALMENNUSTA','ELÄMÄ'])), '')
p=pathlib.Path('data')/(str(d)+'.json');p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(dict(source=source,label=label,items=items),ensure_ascii=False,indent=2))
