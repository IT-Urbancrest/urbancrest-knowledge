#!/usr/bin/env python3
from __future__ import annotations
import hashlib, html, os, re, shutil, sys, unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import recurring_ical_events, requests, yaml
from icalendar import Calendar

TIMEZONE=ZoneInfo("America/New_York")
LOOKAHEAD_DAYS=int(os.getenv("EVENT_LOOKAHEAD_DAYS","120"))
MAX_EVENTS=int(os.getenv("EVENT_MAX_EVENTS","75"))
ROOT=Path(__file__).resolve().parents[1]
REGISTRY_PATH=ROOT/"registry"/"events-live.yaml"
INDEX_PATH=ROOT/"knowledge"/"events"/"upcoming-events.md"
GENERATED_DIR=ROOT/"knowledge"/"events"/"generated"

def clean_text(value):
    if value is None: return ""
    text=html.unescape(str(value)).replace("\\n","\n").replace("\\,",",").replace("\\;",";")
    text=re.sub(r"<[^>]+>","",text); text=re.sub(r"\r\n?","\n",text)
    text=re.sub(r"[ \t]+"," ",text); text=re.sub(r"\n{3,}","\n\n",text)
    return text.strip()

def as_local_datetime(value):
    if isinstance(value,datetime):
        if value.tzinfo is None: value=value.replace(tzinfo=TIMEZONE)
        return value.astimezone(TIMEZONE),False
    if isinstance(value,date): return datetime.combine(value,datetime.min.time(),tzinfo=TIMEZONE),True
    raise TypeError(type(value))

def iso_value(dt,all_day): return dt.date().isoformat() if all_day else dt.isoformat()
def stable_event_id(uid,start): return 'event-'+hashlib.sha256(f'{uid}|{start.isoformat()}'.encode()).hexdigest()[:16]
def slugify(value):
    value=unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode('ascii')
    return re.sub(r'[^a-zA-Z0-9]+','-',value).strip('-').lower() or 'event'
def yq(value): return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'
def format_day(dt): return dt.strftime('%A, %B %-d, %Y')
def format_time(dt): return dt.strftime('%-I:%M %p').replace(':00 ',' ')
def format_event_time(start,end,all_day):
    if all_day:
        final=end-timedelta(days=1)
        return f'{format_day(start)} through {format_day(final)}' if final.date()>start.date() else format_day(start)
    if start.date()==end.date(): return f'{format_day(start)}, {format_time(start)}–{format_time(end)}'
    return f'{format_day(start)} at {format_time(start)} through {format_day(end)} at {format_time(end)}'

def write_event_article(event,generated_at):
    start,end=event['_start_dt'],event['_end_dt']
    slug=f"{start.strftime('%Y-%m-%d')}-{slugify(str(event['title']))}-{str(event['id'])[-6:]}"
    rel=f'knowledge/events/generated/{slug}.md'; path=ROOT/rel
    tags=['event','calendar','upcoming']; low=str(event['title']).lower()
    for kw in ['kids','children','student','students','men','women','missions','worship','family']:
        if kw in low: tags.append(kw)
    lines=['---',f"id: events.live.{event['id']}",'version: 1.0','status: published','priority: 90',f"title: {yq(str(event['title']))}",f"summary: {yq('Live event synchronized from the Urbancrest calendar.')}",'category: [events]','intent:','  primary: event_details','  secondary: [upcoming_events, calendar, schedule]','audience: [everyone]','answer_style: helpful','confidence: high','owner:','  ministry: church_office','review:','  doctrinal: not_required','  factual: automated','tags: ['+', '.join(tags)+']','search_terms:',f"  - {yq(str(event['title']))}",f"  - {yq('When is '+str(event['title'])+'?')}",f"  - {yq('Tell me about '+str(event['title']))}",'resources:','  - events.live',f"event_id: {event['id']}",f"event_start: {yq(str(event['start']))}",f"event_end: {yq(str(event['end']))}",f"all_day: {'true' if event['all_day'] else 'false'}",f'last_generated: {generated_at}','---','',f"# {event['title']}",'',f"**{format_event_time(start,end,bool(event['all_day']))}**",'']
    if event.get('location'): lines += [f"**Location:** {event['location']}",'']
    if event.get('description'): lines += [str(event['description']),'']
    if event.get('url'): lines += [f"More information: {event['url']}",'']
    lines += ["This event information is synchronized automatically from Urbancrest's live calendar.",'']
    path.write_text('\n'.join(lines),encoding='utf-8'); return rel

def main():
    feed=os.getenv('ICAL_FEED_URL','').strip()
    if not feed: print('ICAL_FEED_URL is not set.',file=sys.stderr); return 1
    if feed.startswith('webcal://'): feed='https://'+feed[len('webcal://'):]
    response=requests.get(feed,timeout=30,headers={'User-Agent':'Urbancrest-Knowledge-Event-Sync/1.1'}); response.raise_for_status()
    calendar=Calendar.from_ical(response.content); now=datetime.now(TIMEZONE)
    components=recurring_ical_events.of(calendar).between(now-timedelta(days=1),now+timedelta(days=LOOKAHEAD_DAYS))
    events=[]
    for c in components:
        status=clean_text(c.get('STATUS','CONFIRMED')).upper()
        if status=='CANCELLED': continue
        title=clean_text(c.get('SUMMARY')) or 'Untitled Event'; uid=clean_text(c.get('UID')) or title
        start,all_day=as_local_datetime(c.decoded('DTSTART'))
        if c.get('DTEND') is not None:
            end,end_all_day=as_local_datetime(c.decoded('DTEND')); all_day=all_day and end_all_day
        elif c.get('DURATION') is not None: end=start+c.decoded('DURATION')
        else: end=start+(timedelta(days=1) if all_day else timedelta(hours=1))
        if end<now: continue
        events.append({'id':stable_event_id(uid,start),'uid':uid,'title':title,'start':iso_value(start,all_day),'end':iso_value(end,all_day),'all_day':all_day,'location':clean_text(c.get('LOCATION')) or None,'description':clean_text(c.get('DESCRIPTION')) or None,'url':clean_text(c.get('URL')) or None,'status':status.lower(),'_start_dt':start,'_end_dt':end})
    events.sort(key=lambda e:e['_start_dt']); events=events[:MAX_EVENTS]; generated_at=datetime.now(timezone.utc).isoformat()
    if GENERATED_DIR.exists(): shutil.rmtree(GENERATED_DIR)
    GENERATED_DIR.mkdir(parents=True,exist_ok=True)
    for e in events: e['knowledge_file']=write_event_article(e,generated_at)
    registry_events=[{k:v for k,v in e.items() if not k.startswith('_') and v is not None} for e in events]
    REGISTRY_PATH.write_text(yaml.safe_dump({'version':'1.1','generated_at':generated_at,'timezone':'America/New_York','source':'planning_center_ical','lookahead_days':LOOKAHEAD_DAYS,'event_count':len(registry_events),'events':registry_events},sort_keys=False,allow_unicode=True,width=1000),encoding='utf-8')
    lines=['---','id: events.upcoming.live','version: 1.1','status: published','priority: 100','title: Upcoming Events','summary: Live upcoming events synchronized from the Urbancrest calendar.','category: [events]','intent:','  primary: upcoming_events','  secondary: [calendar, schedule, whats_happening]','audience: [everyone]','answer_style: helpful','confidence: high','owner:','  ministry: church_office','review:','  doctrinal: not_required','  factual: automated','tags: [events, calendar, upcoming, schedule]','resources:','  - events.live',f'last_generated: {generated_at}','---','','# Upcoming Events','',"This page is generated automatically from Urbancrest's live calendar.",'']
    if not events: lines += ['There are currently no upcoming events listed in the calendar.','']
    for e in events:
        lines += [f"## {e['title']}",'',f"**{format_event_time(e['_start_dt'],e['_end_dt'],bool(e['all_day']))}**",'']
        if e.get('location'): lines += [f"**Location:** {e['location']}",'']
        if e.get('description'):
            d=str(e['description']); lines += [(d if len(d)<=400 else d[:397].rstrip()+'...'),'']
        lines += [f"Detailed event file: `{e['knowledge_file']}`",'']
    INDEX_PATH.write_text('\n'.join(lines).rstrip()+'\n',encoding='utf-8')
    print(f'Wrote {len(events)} events.'); return 0
if __name__=='__main__': raise SystemExit(main())
