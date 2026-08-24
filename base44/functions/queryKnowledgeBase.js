// Urbancrest Knowledge Query v0.10.34 - all dinner menus stop at last known menu
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.40';
const SEARCH_INDEX_URL =
'https://raw.githubusercontent.com/IT-Urbancrest/urbancrest-knowledge/main/runtime/search-index.json';
const COMMITS_URL =
'https://api.github.com/repos/IT-Urbancrest/urbancrest-knowledge/commits/main';
const SHA_CHECK_TTL_MS = 2 * 60 * 1000;
const ADMIN_CACHE_TTL_MS = 60 * 1000;
const STAFF_CACHE_TTL_MS = 5 * 60 * 1000;
const RESPONSE_INSTRUCTIONS = `RESPONSE INSTRUCTIONS (these override any conflicting content in the records):
- Answer warmly and concisely in the voice of a welcoming church.
- Use ONLY the SELECTED KNOWLEDGE RECORDS and SELECTED STAFF PROFILE provided. Do not invent service times, events, staff contacts, policies, phone numbers, email addresses, URLs, crisis resources, or details that are absent from the provided records.
- For calendar or event questions, use the structured start/end, location, and registration fields in the selected records. Return the earliest matching occurrence for a singular request (next/nearest). List upcoming matches in ascending date order for plural requests. Never choose a later recurring occurrence over an earlier matching one.
- When SUGGESTED ACTION LINKS are provided, include them as normal markdown links at the end of your answer when they support the next step. When multiple links are provided, include ALL of them. Do not add other links, and never invent links.
- All links must use the urbancrest.church domain, an exact churchcenter.com registration URL present in a selected event record, the churchcenter.com domain for provided action links, approved map provider domains (www.google.com, maps.apple.com) from the action-link registry, or notes.subsplash.com when that exact notes URL is present in a selected sermon record. Never invent, alter, or reconstruct a URL.
- You MUST respond with a JSON object in this exact format:
{"answer": "<your markdown answer here, or UNSURE if you cannot answer from the provided records>", "confidence": <integer 0-100>}
- confidence: an integer from 0 to 100. 100 = fully supported by the provided records, 50 = partial or inferred, 0 = UNSURE / no relevant content. When the answer is only a soft deferral, use a low value (typically 20-40).`
const MARKDOWN_PRESENTATION_INSTRUCTIONS = `
MARKDOWN PRESENTATION RULES:
- Return the answer as clean Markdown.
- Never use Markdown tables.
- Keep a brief conversational introduction when helpful, but do not put a list of results into one long paragraph.
- When the answer contains two or more related items, use a bulleted list.
- When the answer contains steps or a sequence the user should follow, use a numbered list.
- When the answer contains information for two or more dates, sort the dates chronologically.
- When dated results span multiple months, use a level-two heading for each month.
- Use a level-three heading for each individual date.
- Put the details for each date in a bulleted list.
- For menus, put every menu item on its own bullet beneath the applicable date.
- Preserve the wording and facts from the retrieved records.
- Treat search terms, routing aliases/topics, selection rules, and answer_guidance as internal retrieval guidance. Never quote or expose instructions such as "Do not describe..." or lists of routing keywords to the user.
- Use bold text only for short labels, times, or especially important details.
- Place a blank line before and after headings and lists so Markdown renders correctly.
- Do not wrap the answer in a Markdown code fence.
- Do not add headings to a short answer that is naturally one or two sentences.
`;
const STOPWORDS = new Set([
'a', 'an', 'the', 'is', 'are', 'was', 'were', 'do', 'does', 'did', 'what', 'when',
'where', 'who', 'whom', 'how', 'why', 'i', 'you', 'we', 'they', 'it', 'to', 'of',
'in', 'on', 'at', 'for', 'and', 'or', 'but', 'with', 'about', 'your', 'our', 'my',
'me', 'us', 'can', 'could', 'would', 'should', 'will', 'this', 'that', 'these',
'those', 'be', 'been', 'have', 'has', 'had', 'tell', 'please', 'urbancrest',
'church', 'there', 'their', 'his', 'her', 'she', 'he',
]);
const MINISTRY_CANON = {
men: ['men', "men's", 'mens', 'battle ready brotherhood', 'brb'],
women: ['women', "women's", 'womens'],
children: ['children', 'child', 'kids', 'kid', "children's"],
youth: ['youth', 'youths', 'student', 'students', 'teens', 'teen', 'teenager', 'teenagers', 'middle school', 'middle schoolers', 'high school', 'high schoolers'],
preschool: ['preschool'],
nursery: ['nursery'],
senior: ['senior', 'seniors', 'older', "senior's"],
family: ['family', 'families'],
worship: ['worship'],
missions: ['mission', 'missions', 'missional'],
volunteer: ['volunteer', 'volunteers', 'serving', 'serve'],
local_missions: ['local missions', 'local mission', 'local outreach', 'community outreach', 'serving lebanon', 'serve the community'],
stephen_ministry: ['stephen ministry', 'stephen ministries', 'stephen minister', 'stephen ministers'],
legacy_builders: ['legacy builders', 'legacy ministry', 'legacy builders ministry', 'senior adults', 'senior adult ministry', 'adults 50 plus', '50 plus ministry'],
red_barn: ['red barn', 'red barn ministry'],
};
const MINISTRY_OVERVIEW_IDS = {
  youth: 'ministries.students',
  children: 'ministries.kids',
  men: 'ministries.mens_ministry',
  women: 'ministries.womens_ministry',
  worship: 'ministries.worship',
  local_missions: 'ministries.local_missions.overview',
  stephen_ministry: 'ministries.stephen_ministry.overview',
  legacy_builders: 'ministries.legacy_builders.overview',
  red_barn: 'ministries.local_missions.red_barn',
};
const INTENT_KEYWORDS = {
calendar: ['event', 'events', 'happening', 'upcoming', 'calendar', 'going on', 'coming up', 'next ', 'nearest', 'soonest', 'today', 'tonight', 'tomorrow', 'this week', 'this weekend', 'this month', 'this year'],
small_group: ['small group', 'small groups', 'growth group', 'connect group', 'community group'],
sermon_series: ['sermon series', 'message series', 'teaching series', 'current series', 'summer on the mount', 'what are you preaching through', 'what are we preaching through'],
sermon: ['sermon', 'sermons', 'sunday message', 'message from sunday', 'message last sunday', 'preached', 'preach on', 'preach about', 'sermon notes', 'fill-in notes', 'fill in notes', 'message notes', 'what did geoff preach', 'what did dave preach', 'what did david preach'],
staff: ['who oversees', 'who leads', 'who handles', 'who takes care of', 'who manages', 'who runs', 'who is responsible', 'who do i contact', 'who should i contact', 'who should i talk to', 'point person', 'pastor', 'staff', 'director', 'minister', 'oversees', 'leads', 'handles', 'takes care of', 'manages', 'who preaches', 'who is preaching'],
ministry: ["men's", 'mens', "women's", 'womens', 'children', 'youth', 'students', 'student', 'teen', 'teens', 'teenager', 'teenagers', 'middle school', 'high school', 'worship', 'missions', 'mission', 'local missions', 'stephen ministry', 'legacy builders', 'red barn', 'preschool', 'nursery', 'kids', 'senior adult', 'young adult', 'small group', 'family', 'families', 'production', 'creative', 'website', 'livestream', 'audio', 'lighting', 'technology', 'finance', 'giving', 'stewardship', 'facilities', 'guest services', 'member services'],
doctrine: ['believe', 'belief', 'salvation', 'saved', 'baptism', 'baptize', 'theology', 'faith', 'scripture', 'gospel', 'repentance', 'doctrine', 'communion', "lord's supper", 'close communion', 'open communion', 'closed communion', 'stewardship', 'tithe', 'tithing', 'generosity', 'eternal security', 'assurance', 'save me', 'good works', 'earn salvation', 'sin', 'grace', 'jesus', 'christ', 'god', 'lord', 'suicide', 'self harm', 'self-harm', 'unforgivable'],
service_times: ['service time', 'service times', 'sunday service', 'sunday services', 'service hours', 'morning service', 'worship service', 'worship services', 'what time is church', 'what time does church start', 'when does church start', 'when does urbancrest meet', 'when does church meet', 'what time are sunday services', 'what are your sunday service times', 'church start', 'church begin', 'when are services', 'when are worship services'],
location: [
'where are you', 'where are you located', 'where are you at', 'where is urbancrest',
'where is your church', 'where is the church', 'church address', 'your address',
'address', 'location', 'parking', 'located', 'drake road', 'drake rd',
],
parking: ['where do i park', 'where can i park', 'where should i park', 'where should we park', 'parking'],
giving: ['how do i give', 'how can i give', 'give online', 'giving online', 'donate online', 'make a donation', 'online donation'],
livestream: ['livestream', 'live stream', 'watch online', 'watch the service online', 'online service', 'stream the service'],
directions: ['how do i get to', 'how do i get there', 'give me directions', 'directions to', 'take me to', 'navigate to', 'how do i find', 'find the church', 'how to get to', 'how to get there', 'directions'],
registration: ['sign up', 'register', 'registration', 'rsvp', 'enroll', 'how do i join'],
activity_availability: [
'does urbancrest have', 'do you have', 'do you offer', 'does urbancrest offer',
'does the church have', 'does your church have', 'is there', 'are there',
'can i play', 'can we play', 'can i participate', 'can you play',
'do you host', 'does urbancrest host', 'do you provide',
],
schedule: ['when does', 'when do ', 'what time does', 'what time is', 'what days does', 'what is the schedule'],
local_missions_info: ['local missions', 'local mission', 'local outreach', 'community outreach', 'serving lebanon', 'serve the community', 'baskets of hope', 'emergency food', 'food boxes', 'food box', 'school supply', 'school supplies', 'benevolence'],
food_assistance: ['food assistance', 'food help', 'help with food', 'need food', 'i need food', 'get food', 'groceries', 'grocery', 'food box', 'food boxes', 'food pantry', 'how do i get food', 'how can i get food', 'need help with food', 'how can my family get food'],
baskets_of_hope: ['baskets of hope', 'basket of hope'],
};
const TEMPORAL_KEYWORDS = ['next', 'nearest', 'soonest', 'upcoming', 'today', 'tonight', 'tomorrow', 'this week', 'this weekend', 'this month', 'this year', 'soon'];
const SERVICE_TIME_PREFERRED_IDS = new Set(['schedule.weekly', 'schedule.worship.sunday', 'about.services.times']);
const SERVICE_TIME_AUTH = new Set(['service_times', 'sunday_service_times']);
const DIRECTIONS_PREFERRED_IDS = new Set(['visit.directions', 'about.location']);
const DATE_REFERENCE_PHRASES = [
'today', 'tonight', 'tomorrow', 'this sunday', 'next sunday', 'this coming sunday',
'this week', 'this weekend', 'next week', 'this year',
];
const HOLIDAY_PHRASES = [
'christmas', 'christmas eve', 'easter', 'good friday', 'palm sunday', 'maundy thursday',
'ash wednesday', 'pentecost', 'advent', 'new year', "new year's", 'new years', 'thanksgiving',
'independence day', 'july 4th', 'fourth of july', 'memorial day', "labor day", "mother's day",
"father's day",
];
// Module-level caches (persist across warm invocations)
let indexBySha = { sha: '', index: null, ts: 0 };
let lastGoodIndex = null;
let shaCache = { sha: '', ts: 0 };
let staffCache = { ts: 0, list: [] };
let adminCache = { ts: 0, records: [] };
function normalize(text) {
return String(text || '')
.toLowerCase()
.replace(/[’‘]/g, "'")
.trim()
.replace(/\s+/g, ' ');
}
function tokenize(text) {
return normalize(text).split(/[^a-z0-9']+/).filter((t) => t.length > 1);
}
function intentBase(intent) {
return String(intent || '').replace(/s$/, '');
}
function canonMinistry(value) {
const v = normalize(value).replace(/'/g, '');
for (const [canon, variants] of Object.entries(MINISTRY_CANON)) {
if (variants.some((variant) => normalize(variant).replace(/'/g, '') === v)) return canon;
}
return v;
}
function detectIntents(q) {
const nq = normalize(q);
const intents = [];
for (const [intent, keywords] of Object.entries(INTENT_KEYWORDS)) {
if (keywords.some((k) => nq.includes(k))) intents.push(intent);
}
// A dated reference to "the message" is normally a sermon question even when
// the user does not say the word sermon (for example, "the July 19 message").
if (/\b(message|messages)\b/.test(nq) && (
/\b(last sunday|this past sunday|previous sunday)\b/.test(nq) ||
/\b(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sept|sep|october|oct|november|nov|december|dec)\s+\d{1,2}\b/.test(nq) ||
/\b\d{1,2}\/\d{1,2}(?:\/\d{2,4})?\b/.test(nq)
)) {
if (!intents.includes('sermon')) intents.push('sermon');
}
// Explicit belief topics that need deterministic routing. Use regex boundaries
// here instead of short substring keywords so terms such as "gay" do not
// accidentally match unrelated words.
if (
/\b(trinity|triune|transubstantiation|antichrist|anti-christ|man of lawlessness)\b/.test(nq)
|| /\b(lgbtq?|gay|lesbian|bisexual|queer|homosexual(?:ity)?|transgender|nonbinary|same[- ]sex|gender identity|biblical sexuality)\b/.test(nq)
|| /\b(nasb|nkjv|bible translation|bible translations|bible version|bible versions|word[- ]for[- ]word|thought[- ]for[- ]thought|formal equivalence|dynamic equivalence|functional equivalence)\b/.test(nq)
|| /\bwhat (?:bible|translation|version)\b[^.!?]{0,45}\b(use|uses|using|preach|preaches|preaching)\b/.test(nq)
|| /\bwhich (?:bible|translation|version)\b[^.!?]{0,45}\b(use|uses|using|preach|preaches|preaching)\b/.test(nq)
|| /\bwhat bible do (?:you|we)\b/.test(nq)
) {
if (!intents.includes('doctrine')) intents.push('doctrine');
}

// A date-specific Bible-version question is really a sermon-record question.
// "What Bible did Geoff use last Sunday?" should not be answered from the
// pastor's usual translation when a specific sermon may have used something else.
if (
/\b(?:bible|translation|version|nasb|nkjv)\b/.test(nq)
&& /\b(?:preach|preached|sermon|message|used|use)\b/.test(nq)
&& (
DATE_REFERENCE_PHRASES.some((phrase) => nq.includes(phrase))
|| /\b(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sept|sep|october|oct|november|nov|december|dec)\s+\d{1,2}\b/.test(nq)
|| /\b\d{1,2}\/\d{1,2}(?:\/\d{2,4})?\b/.test(nq)
)
) {
if (!intents.includes('sermon')) intents.push('sermon');
}

// Conceptual giving questions are doctrine/stewardship questions, while
// transactional questions such as "How do I give online?" retain the existing
// `giving` operational intent and are excluded from direct doctrine routing.
if (/\b(why should (?:christians?|believers?) give|how should (?:christians?|believers?) give|biblical giving|christian giving)\b/.test(nq)) {
if (!intents.includes('doctrine')) intents.push('doctrine');
}
if (intents.length === 0) intents.push('general');
return intents;
}
function addIntent(intents, intent) {
if (!intents.includes(intent)) intents.push(intent);
}
function applyBenevolenceIntents(question, intents, ministries) {
const nq = normalize(question);
const rent = /\b(rent|rental assistance|mortgage)\b/.test(nq);
const utilities = /\b(utilities|utility|electric bill|power bill|water bill|natural gas bill|gas utility|gas bill)\b/.test(nq);
const vehicleGas = /\b(gas card|gasoline|fuel|gas for (my|the) car|gas to get|transportation cost|transportation costs|help with gas)\b/.test(nq)
|| (/\b(can|could|does|do)\b.*\b(help|assist)\b.*\bgas\b/.test(nq) && !utilities);
const hardship = /\b(financial help|financial assistance|financial hardship|struggling financially|financially struggling|help with bills|help paying|basic needs|benevolence|assistance with expenses|help with expenses)\b/.test(nq);
if (!(rent || utilities || vehicleGas || hardship)) return;
addIntent(intents, 'benevolence_assistance');
if (rent) addIntent(intents, 'rent_assistance');
if (utilities) addIntent(intents, 'utility_assistance');
if (vehicleGas) addIntent(intents, 'gas_assistance');
if (hardship && !rent && !utilities && !vehicleGas) addIntent(intents, 'financial_hardship');
if (!ministries.includes('local_missions')) ministries.push('local_missions');
}
function detectMinistries(q) {
const nq = ' ' + normalize(q) + ' ';
const found = [];
for (const [canon, variants] of Object.entries(MINISTRY_CANON)) {
if (variants.some((variant) => {
const escaped = normalize(variant).replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/'/g, "'?");
return new RegExp(`\\b${escaped}\\b`).test(nq);
})) found.push(canon);
}
if (found.includes('local_missions') && /\b(local missions?|local outreach|community outreach)\b/.test(nq)) {
return [...new Set(found.filter((m) => m !== 'missions'))];
}
return [...new Set(found)];
}
function cleanMinistryIdentity(value) {
let text = normalize(value)
.replace(/[?!.,:;]+$/g, '')
.replace(/^what\s+(?:is|are)\s+/i, '')
.replace(/^what\s+does\s+urbancrest\s+(?:offer|have)\s+(?:for\s+)?/i, '')
.replace(/^what\s+do\s+you\s+(?:offer|have)\s+(?:for\s+)?/i, '')
.replace(/^tell\s+me\s+about\s+/i, '')
.replace(/^(?:your|our|my|the)\s+/i, '')
.replace(/^urbancrest(?:'s)?\s+/i, '')
.trim();
return text;
}
function ministryIdentityVariants(value) {
const base = cleanMinistryIdentity(value);
const variants = new Set();
if (base) variants.add(base);
if (base.endsWith(' ministry')) variants.add(base.slice(0, -9).trim());
if (base.startsWith('urbancrest ')) variants.add(base.slice(11).trim());
return [...variants].filter(Boolean);
}
function isMinistryOverviewShape(record) {
if (!record || record.record_type !== 'knowledge') return false;
const id = String(record.id || '');
const path = String(record.path || '');
if (/^ministries\.[^.]+$/.test(id)) return true;
if (/\.overview$/.test(id)) return true;
if (/^knowledge\/ministries\/[^/]+\.md$/.test(path)) return true;
return false;
}
function exactMinistryIdentityMatch(record, subject) {
if (!record || !subject) return false;
const subjectVariants = new Set(ministryIdentityVariants(subject));
if (subjectVariants.size === 0) return false;
const fields = [
record.title || '',
...(record.tags || []),
...(record.search_terms || []),
];
for (const field of fields) {
for (const variant of ministryIdentityVariants(field)) {
if (subjectVariants.has(variant)) return true;
}
}
return false;
}
function recordCanonicalMinistryKeys(record) {
const values = [
...(record?.ministries || []),
record?.title || '',
...(record?.tags || []),
];
const keys = new Set();
for (const value of values) {
for (const variant of ministryIdentityVariants(value)) {
const key = canonMinistry(variant);
if (Object.prototype.hasOwnProperty.call(MINISTRY_CANON, key)) keys.add(key);
}
}
return keys;
}
function isBroadMinistryOverviewCue(question) {
const nq = normalize(question).replace(/[?!.,]+$/g, '').trim();
if (/^(tell\s+me\s+about|what\s+do\s+you\s+have\s+for|what\s+does\s+urbancrest\s+have\s+for|what\s+do\s+you\s+offer\s+for|what\s+does\s+urbancrest\s+offer\s+for|do\s+you\s+have\s+a\s+ministry\s+for|does\s+urbancrest\s+have\s+a\s+ministry\s+for)\b/.test(nq)) return true;
// A short bare ministry name such as "Local Missions", "Legacy Builders", or
// "Stephen Ministry" is naturally an overview request.
if (!/\b(who|when|where|how|why|which|schedule|meet|meeting|event|events|register|sign\s+up|cost|price|age|grade|grades)\b/.test(nq)
    && tokenize(nq).length >= 1 && tokenize(nq).length <= 4) return true;
return false;
}
function selectMinistryOverviewRecords(all, question, intents, ministries) {
// Leadership/contact, dated, schedule, and event questions need their specialized routes.
if (isStaffLikeQuestion(question, intents) || isStaffOwnershipQuestion(question, intents) || isStaffContactDetailQuestion(question)) return null;
if ((intents || []).some((intent) => ['calendar', 'schedule', 'service_times', 'registration', 'sermon', 'sermon_series'].includes(intent))) return null;
if (isTemporal(question)) return null;

const subject = cleanMinistryIdentity(question);
const broadCue = isBroadMinistryOverviewCue(question);
const queryKeys = new Set((ministries || []).map(canonMinistry));
// Derive a canonical ministry key from the simplified subject as well. This catches
// audience wording such as "teenagers", "my kids", and "senior adults".
for (const key of detectMinistries(subject)) queryKeys.add(canonMinistry(key));

// Broad ministry questions should resolve to the canonical overview article before
// fuzzy/tag/search-term scoring is allowed. This prevents a secondary article whose
// tags happen to contain a broad audience word (for example "students" on School
// Supply Giveaway) from beating the actual Student Ministry overview.
if (broadCue && queryKeys.size > 0) {
  for (const key of queryKeys) {
    const preferredId = MINISTRY_OVERVIEW_IDS[key];
    if (!preferredId) continue;
    const preferred = (all || []).find((record) => record && record.record_type === 'knowledge' && record.id === preferredId);
    if (preferred) return { records: [preferred], score: 2000, canonicalKey: key };
  }
}

const ranked = [];
for (const record of (all || [])) {
if (!record || record.record_type !== 'knowledge') continue;
const categories = (record.category || []).map(normalize);
if (!categories.includes('ministries') && !String(record.id || '').startsWith('ministries.')) continue;

const overviewShape = isMinistryOverviewShape(record);
const exactIdentity = exactMinistryIdentityMatch(record, subject);
const recordKeys = recordCanonicalMinistryKeys(record);
const canonicalMatch = [...queryKeys].some((key) => recordKeys.has(key));

// Exact named ministry/article matches are safe. Otherwise only a canonical top-level
// overview may answer broad audience questions such as "What do you have for teenagers?".
if (!exactIdentity && !(broadCue && overviewShape && canonicalMatch)) continue;

let score = 0;
// For broad audience/ministry questions, do not reward an exact match that came only
// from a tag or search term on a secondary FAQ/article. Canonical overview shape and
// ministry identity should dominate.
if (exactIdentity) score += broadCue && !overviewShape ? 120 : 700;
if (overviewShape) score += 500;
if (canonicalMatch) score += 360;
if ((record.intents || []).map(normalize).includes('ministry_info')) score += 70;
if (record.authoritative === true) score += 30;
score += Math.min(Number(record.priority || 0), 150) / 10;
ranked.push({ record, score });
}
ranked.sort((a, b) => b.score - a.score || (b.record.priority || 0) - (a.record.priority || 0));
if (!ranked.length) return null;
return { records: [ranked[0].record], score: ranked[0].score };
}
function isTemporal(q) {
const nq = normalize(q);
return TEMPORAL_KEYWORDS.some((k) => nq.includes(k));
}
function isSingularRequest(q) {
const nq = ' ' + normalize(q) + ' ';
if (/\b(next|nearest|soonest|first|earliest)\b/.test(nq)) return true;
if (/\b(all|every|list|each|events|groups|upcoming events|this week|this weekend|this month)\b/.test(nq)) return false;
return true;
}
function bigrams(text) {
const tokens = tokenize(text);
const set = new Set();
for (let i = 0; i < tokens.length - 1; i++) set.add(tokens[i] + ' ' + tokens[i + 1]);
return set;
}
function nyNow() {
try {
return new Date().toLocaleString('en-US', {
timeZone: 'America/New_York',
weekday: 'long',
year: 'numeric',
month: 'long',
day: 'numeric',
hour: 'numeric',
minute: '2-digit',
timeZoneName: 'short',
});
} catch {
return new Date().toString();
}
}
async function fetchJson(url, headers = {}) {
const res = await fetch(url, { headers: { 'User-Agent': 'urbancrest-kb', ...headers } });
if (!res.ok) throw new Error(`fetch ${url} failed (${res.status})`);
return await res.json();
}
async function fetchJsonWithRetry(url, headers = {}, attempts = 3) {
let lastError = null;
for (let attempt = 0; attempt < attempts; attempt++) {
try {
return await fetchJson(url, headers);
} catch (error) {
lastError = error;
if (attempt < attempts - 1) {
await new Promise((resolve) => setTimeout(resolve, 150 * (attempt + 1)));
}
}
}
throw lastError || new Error(`fetch ${url} failed`);
}
async function getLatestSha() {
if (shaCache.sha && Date.now() - shaCache.ts < SHA_CHECK_TTL_MS) return shaCache.sha;
try {
const data = await fetchJsonWithRetry(COMMITS_URL, { Accept: 'application/vnd.github+json' }, 2);
const sha = data?.sha || '';
shaCache = { sha, ts: Date.now() };
return sha;
} catch {
return shaCache.sha || '';
}
}
async function getSearchIndex() {
const sha = await getLatestSha();
if (indexBySha.index && sha && indexBySha.sha === sha) return indexBySha.index;
if (indexBySha.index && !sha && Date.now() - indexBySha.ts < SHA_CHECK_TTL_MS) return indexBySha.index;
try {
const index = await fetchJsonWithRetry(SEARCH_INDEX_URL, {}, 3);
indexBySha = { sha: sha || index?.repository_version || 'unknown', index, ts: Date.now() };
lastGoodIndex = index;
return index;
} catch {
if (lastGoodIndex) return lastGoodIndex;
if (indexBySha.index) return indexBySha.index;
throw new Error('search index unavailable');
}
}
async function getStaffCollection(base44) {
if (staffCache.list.length && Date.now() - staffCache.ts < STAFF_CACHE_TTL_MS) return staffCache.list;
const list = await base44.asServiceRole.entities.Staff.list('-order', 200);
staffCache = { ts: Date.now(), list };
return list;
}
function findStaffByKey(list, key) {
const wanted = normalize(key);
return list.find((s) => normalize(s.key) === wanted) || null;
}
function toAdminRecord(e) {
const tags = Array.isArray(e.tags) ? e.tags : [];
return {
id: `admin.${e.id}`,
record_type: e.category === 'sermon_transcript' ? 'sermon' : 'faq',
source: 'base44_admin',
title: e.title || '',
summary: e.summary || (e.content || '').slice(0, 200),
content: e.content || '',
priority: typeof e.priority === 'number' ? e.priority : 70,
intents: [],
tags,
search_terms: Array.isArray(e.search_terms) ? e.search_terms : [],
ministries: Array.isArray(e.ministries) ? e.ministries : [],
audiences: Array.isArray(e.audiences) ? e.audiences : [],
date: e.date || '',
speaker: e.speaker || '',
};
}
async function getApprovedAdminRecords(base44) {
if (adminCache.records.length && Date.now() - adminCache.ts < ADMIN_CACHE_TTL_MS) return adminCache.records;
let entries = [];
try {
entries = await base44.asServiceRole.entities.KnowledgeEntry.filter(
{ status: 'published', approved: true },
'-created_date',
200,
);
} catch {
return adminCache.records;
}
const records = entries
.filter((e) => e && e.status === 'published' && e.approved === true)
.map(toAdminRecord);
adminCache = { ts: Date.now(), records };
return records;
}
function scoreRecord(record, normQ, tokens, intents, ministries, scheduleCtx) {
let score = 0;
const title = normalize(record.title || '');
const searchTerms = (record.search_terms || []).map(normalize);
// exact title or search-term match: +100
if (title && title.length >= 3 && (normQ.includes(title) || (normQ.length >= 3 && title.includes(normQ)))) score += 100;
else if (searchTerms.some((t) => t && t.length >= 3 && (normQ.includes(t) || t.includes(normQ)))) score += 100;
// matching intent: +60
const recIntents = (record.intents || []).map(normalize);
if (recIntents.some((i) => intents.some((di) => intentBase(di) === intentBase(i)))) score += 60;
// matching ministry or audience: +50
const recMin = (record.ministries || []).map(canonMinistry);
const recAud = (record.audiences || []).map(canonMinistry);
if (recMin.some((m) => ministries.includes(m)) || recAud.some((a) => ministries.includes(a))) score += 50;
// matching tag: +30
const recTags = (record.tags || []).map(normalize);
if (recTags.some((t) => tokens.includes(t))) score += 30;
// Local Missions deterministic boosts (applied before candidate truncation).
if (ministries.includes('local_missions')) {
const recMinCanon = (record.ministries || []).map(canonMinistry);
// exact local_missions ministry match: +150
if (recMinCanon.includes('local_missions')) score += 150;
// matching local_missions_info intent: +140
if (intents.includes('local_missions_info') && recIntents.includes('local_missions_info')) score += 140;
// phrase-level Local Missions match: +100
const lmPhrases = ['local missions', 'local mission', 'local outreach', 'community outreach'];
if (lmPhrases.some((p) => normQ.includes(p))) {
const allText = normalize(`${record.title || ''} ${record.summary || ''} ${record.content || ''} ${(record.search_terms || []).join(' ')}`);
if (lmPhrases.some((p) => allText.includes(p))) score += 100;
}
// authoritative === true when authoritative_for matches detected intent: +60
if (record.authoritative === true) {
const authFor = (record.authoritative_for || []).map(normalize);
if (authFor.some((a) => intents.includes(a))) score += 60;
}
}
// Food assistance deterministic boosts (applied before candidate truncation).
if (intents.includes('food_assistance') || intents.includes('baskets_of_hope')) {
const recId = record.id || '';
const recIntentsNorm = (record.intents || []).map(normalize);
const isEmergency = isEmergencyFoodQuestion(normQ);
// exact food_assistance intent match: +180
if (intents.includes('food_assistance') && recIntentsNorm.includes('food_assistance')) score += 180;
// food_assistance record for general (non-emergency) food help: +220
if (!isEmergency && recId === 'ministries.local_missions.food_assistance') score += 220;
// emergency_food_boxes record for explicit emergency/urgent-before-next-distribution: +220
if (isEmergency && recId === 'ministries.local_missions.emergency_food_boxes') score += 220;
// baskets_of_hope record for "what is baskets of hope" questions: +220
if (intents.includes('baskets_of_hope') && recId === 'ministries.local_missions.baskets_of_hope') score += 220;
}
// Benevolence and financial-assistance boosts (before candidate truncation).
if (intents.includes('benevolence_assistance')) {
const recIntentsNorm = (record.intents || []).map(normalize);
if (recIntentsNorm.includes('benevolence_assistance')) score += 180;
for (const specific of ['rent_assistance', 'utility_assistance', 'gas_assistance', 'financial_hardship']) {
if (intents.includes(specific) && recIntentsNorm.includes(specific)) score += 200;
}
const preferredBenevolenceIds = {
rent_assistance: 'ministries.local_missions.rent_utility_assistance',
utility_assistance: 'ministries.local_missions.rent_utility_assistance',
gas_assistance: 'ministries.local_missions.gas_assistance',
financial_hardship: 'ministries.local_missions.financial_hardship',
};
for (const [intent, preferredId] of Object.entries(preferredBenevolenceIds)) {
if (intents.includes(intent) && record.id === preferredId) score += 260;
}
if (!Object.keys(preferredBenevolenceIds).some((intent) => intents.includes(intent))
&& record.id === 'ministries.local_missions.benevolence') score += 220;
if (record.authoritative === true) {
const authFor = (record.authoritative_for || []).map(normalize);
if (authFor.some((a) => intents.includes(a))) score += 80;
}
}
// activity / fuzzy token match against title, activity aliases, search terms, tags: +90
if (activityMatchedTokens(record, tokens, true).length > 0) score += 90;
// Generic schedule boosts (applied before candidate truncation).
if (scheduleCtx && scheduleCtx.isScheduleQ) {
// schedule record for a schedule question: +180
if (record.record_type === 'schedule') score += 180;
// exact schedule or ministry alias phrase match: +220
const scheduleAliases = (record.schedule_aliases || []).map(normalize);
const ministryAliases = (record.ministry_aliases || []).map(normalize);
const allAliases = [...scheduleAliases, ...ministryAliases];
if (allAliases.some((a) => a && a.length >= 3 && normQ.includes(a))) score += 220;
// matching ministry: +120
if (scheduleCtx.ministry) {
const recMin = (record.ministries || []).map(normalize);
if (recMin.includes(scheduleCtx.ministry)) score += 120;
}
// authoritative === true: +40
if (record.authoritative === true) score += 40;
}
// phrase match in summary: +25
const summaryBigrams = bigrams(record.summary || '');
const qBigrams = bigrams(normQ);
for (const b of qBigrams) {
if (summaryBigrams.has(b)) { score += 25; break; }
}
// token match in content: +5 per unique token
const contentTokens = new Set(tokenize(record.content || ''));
let tokMatches = 0;
for (const t of tokens) if (contentTokens.has(t)) tokMatches++;
score += tokMatches * 5;
// priority contribution: priority / 10
score += (record.priority || 0) / 10;
return score;
}
// Normalize ministry tokens: lowercase, strip apostrophes, collapse spaces.
function normalizeMinistryToken(text) {
return normalize(text).replace(/['']/g, '');
}
// Check whether a canonical ministry key matches an event record's ministries,
// audiences, tags, or title. Uses normalized apostrophes and word-boundary
// matching so "men's" / "mens" / "men" all match "Men's Breakfast" and
// "Men's Ministry Breakfast".
function ministryVariantRegex(value) {
  const normalized = normalizeMinistryToken(value);
  if (!normalized) return null;
  const escaped = normalized.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(^|[^a-z0-9])${escaped}([^a-z0-9]|$)`, 'i');
}
function textHasMinistryVariant(text, ministry) {
  const canon = canonMinistry(ministry);
  const normalizedText = normalizeMinistryToken(text);
  if (!normalizedText) return false;
  return (MINISTRY_CANON[canon] || []).some((variant) => {
    const pattern = ministryVariantRegex(variant);
    return pattern ? pattern.test(normalizedText) : false;
  });
}
function specificEventCategoryForMinistry(ministry) {
  const canon = canonMinistry(ministry);
  return {
    youth: ['student_event', 'students_event', 'youth_event'],
    children: ['kids_event', 'children_event'],
    men: ['mens_event', 'men_event'],
    women: ['womens_event', 'women_event'],
    worship: ['worship_event'],
    local_missions: ['local_missions_event'],
    senior: ['senior_event'],
    family: ['family_event'],
  }[canon] || [];
}
function overviewExplicitlyMentionsEvent(overviewRecord, eventRecord) {
  if (!overviewRecord || !eventRecord) return false;
  const overviewText = normalizeMinistryToken(`${overviewRecord.title || ''} ${overviewRecord.summary || ''} ${overviewRecord.content || ''}`);
  if (!overviewText) return false;
  const candidates = [
    ...(eventRecord.activity_aliases || []),
    ...(eventRecord.event_aliases || []),
    eventRecord.title || '',
  ]
    .map((value) => normalizeMinistryToken(value).replace(/^urbancrest\s+/, '').trim())
    .filter((value) => value.length >= 7);
  return candidates.some((value) => overviewText.includes(value));
}
function boundedPhraseMatches(text, phrase) {
  const haystack = normalizeMinistryToken(text);
  const needle = normalizeMinistryToken(phrase);
  if (!haystack || !needle) return false;
  const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(^|[^a-z0-9])${escaped}([^a-z0-9]|$)`, 'i').test(haystack);
}

function eventHasConflictingGenderSignal(canon, record) {
  if (!record) return false;
  const text = `${record.title || ''} ${(record.activity_aliases || []).join(' ')} ${(record.event_aliases || []).join(' ')} ${record.summary || ''} ${record.content || ''}`;
  if (canon === 'men') {
    const womenSignal = ["women's", 'womens', 'women'].some((phrase) => boundedPhraseMatches(text, phrase));
    const menSignal = ["men's", 'mens', 'men', 'battle ready brotherhood'].some((phrase) => boundedPhraseMatches(text, phrase));
    return womenSignal && !menSignal;
  }
  if (canon === 'women') {
    const menSignal = ["men's", 'mens', 'men', 'battle ready brotherhood'].some((phrase) => boundedPhraseMatches(text, phrase));
    const womenSignal = ["women's", 'womens', 'women'].some((phrase) => boundedPhraseMatches(text, phrase));
    return menSignal && !womenSignal;
  }
  return false;
}

function ministryEventMatchScore(ministry, record, overviewRecord = null) {
  if (!record || record.record_type !== 'event') return 0;
  const canon = canonMinistry(ministry);
  if (!Object.prototype.hasOwnProperty.call(MINISTRY_CANON, canon)) return 0;

  // Explicit contradictory audience wording in the event itself beats noisy generated
  // metadata. This prevents Women's events from appearing under Men's Ministry and vice versa.
  if (eventHasConflictingGenderSignal(canon, record)) return 0;

  let score = 0;

  // Highest-confidence signals: the event title/name itself, an explicit Planning Center
  // registration category, or a ministry-specific event category.
  const titleFields = [record.title || '', ...(record.activity_aliases || []), ...(record.event_aliases || [])];
  if (titleFields.some((value) => textHasMinistryVariant(value, canon))) score = Math.max(score, 170);

  const registrationCategories = record.registration_categories || record.registrationCategories || [];
  if (registrationCategories.some((value) => textHasMinistryVariant(value, canon))) score = Math.max(score, 165);

  const eventCategory = normalize(record.event_category || record.eventCategory || '');
  if (specificEventCategoryForMinistry(canon).includes(eventCategory)) score = Math.max(score, 155);

  // Some recurring ministry events have branded names that do not contain the ministry name.
  // A direct mention in the canonical overview is strong evidence.
  if (overviewExplicitlyMentionsEvent(overviewRecord, record)) score = Math.max(score, 150);

  // A ministry-specific phrase in the event's public description can establish relevance
  // for branded events such as P U R S U E or AWANA. Use bounded phrase matching so
  // "men's ministry" can never match inside "women's ministry".
  const descriptiveText = `${record.summary || ''} ${record.content || ''} ${record.details || ''}`;
  const specificPhrases = {
    youth: ['student ministry', 'youth service', 'youth group', 'grades 7-12', 'grades 7 through 12'],
    children: ['kids ministry', 'children ministry', "children's ministry", 'awana', 'vbs'],
    preschool: ['preschool'],
    nursery: ['nursery'],
    men: ["men's ministry", 'mens ministry', 'battle ready brotherhood'],
    women: ["women's ministry", 'womens ministry'],
    local_missions: ['local missions', 'baskets of hope', 'red barn', 'trail of treats', 'school supply giveaway', 'block party'],
    legacy_builders: ['legacy builders'],
    stephen_ministry: ['stephen ministry', 'stephen minister'],
  }[canon] || [];
  if (specificPhrases.some((phrase) => boundedPhraseMatches(descriptiveText, phrase))) {
    score = Math.max(score, 145);
  }

  // Deliberately do NOT qualify an event from generated `ministries`, `audiences`, or
  // generic tags alone. Those fields are useful for broad search but can contain
  // heuristic false positives (for example "Child's Hope" -> kids or "workmen" -> men).
  return score;
}
function ministryMatchesEvent(ministry, record, overviewRecord = null) {
  return ministryEventMatchScore(ministry, record, overviewRecord) >= 145;
}

// Determine whether the user is asking for a specific upcoming event occurrence.
// Prevents "next" as a constraint ("before the next distribution") and recurring
// program overviews ("each year") from triggering event-only filtering.
function isUpcomingEventQuestion(question) {
const nq = normalize(question);
// Food assistance questions should not enter event-only mode
if (/\b(food\s+assistance|food\s+help|help\s+with\s+food|need\s+food|food\s+box|food\s+boxes|groceries|grocery|food\s+pantry|emergency\s+food)\b/.test(nq)) return false;
// "before the next" / "until the next" - constraint, not event request
if (/\bbefore\s+(the\s+)?next\b/.test(nq)) return false;
if (/\buntil\s+(the\s+)?next\b/.test(nq)) return false;
// "each year", "every year", "annually" - recurring program overview
if (/\b(each|every)\s+year\b/.test(nq) || /\bannually\b/.test(nq)) return false;
// "what does X do" - ministry overview, not event request
if (/\bwhat\s+(does|do)\b/.test(nq) && !/\b(when|where|what\s+time)\b/.test(nq)) return false;
return [
/\b(next|nearest|soonest|upcoming)\b.*\b(event|events|meeting|gathering|breakfast|lunch|dinner|conference|party|outreach|service|class)\b/,
/\bwhat\s+is\s+(the\s+)?next\b/,
/\bwhen\s+is\s+(the\s+)?next\b/,
/\bwhen\s+is\b.*\bthis\s+year\b/,
/\b(events?|activities)\b.*\bcoming\s+up\b/,
/\bhappening\b.*\b(today|tonight|tomorrow|this\s+week|this\s+weekend|this\s+month|this\s+year)\b/,
/\bwhat\s+.*\b(events?|activities)\b.*\b(today|tonight|tomorrow|this\s+week|this\s+weekend|this\s+month|this\s+year)\b/,
/\b(today|tonight|tomorrow|this\s+week|this\s+weekend|this\s+month|this\s+year)\b.*\b(events?|activities|meeting|gathering)\b/,
].some((pattern) => pattern.test(nq));
}
// Detect emergency food questions: explicit "emergency food box" requests, or
// users who indicate they are already receiving Baskets of Hope and cannot wait
// until the next distribution. These should route to the emergency_food_boxes
// record instead of the general food_assistance record.
function isEmergencyFoodQuestion(normQ) {
if (/\bemergency\s+food\s+box/.test(normQ)) return true;
if (/\bemergency\s+food/.test(normQ)) return true;
if (/\b(already\s+receiv|already\s+get|currently\s+receiv|already\s+connected|already\s+enrolled|already\s+part\s+of)/.test(normQ) &&
/\b(before|until|cannot\s+wait|can't\s+wait|can\s+not\s+wait)\b/.test(normQ)) return true;
if (/(cannot\s+wait|can't\s+wait|can\s+not\s+wait)/.test(normQ) &&
/\b(next|until|before)\b/.test(normQ) &&
/\b(distribution|baskets?\s+of\s+hope)\b/.test(normQ)) return true;
return false;
}
const EVENT_QUERY_STOPWORDS = new Set([
...STOPWORDS,
'event', 'events', 'activity', 'activities', 'happening', 'upcoming', 'next', 'nearest',
'soonest', 'today', 'tonight', 'tomorrow', 'week', 'weekend', 'month', 'year', 'ministry',
'meeting', 'meetings', 'gathering', 'gatherings', 'coming',
]);
function nyDateKey(ms) {
const parts = new Intl.DateTimeFormat('en-CA', {
timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit',
}).formatToParts(new Date(ms));
const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
return `${values.year}-${values.month}-${values.day}`;
}
function addDaysToDateKey(key, days) {
const [year, month, day] = key.split('-').map(Number);
const date = new Date(Date.UTC(year, month - 1, day + days));
return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}-${String(date.getUTCDate()).padStart(2, '0')}`;
}
function weekdayIndexForDateKey(key) {
const [year, month, day] = key.split('-').map(Number);
return new Date(Date.UTC(year, month - 1, day)).getUTCDay();
}
function eventStartMs(record) {
return new Date(record.sort_start_utc || record.start_utc || record.starts_at || 0).getTime();
}


const WEDNESDAY_DINNER_TITLE = 'wednesday night dinner';
const DINNER_MONTH_NAME_TO_NUMBER = {
january: 1, february: 2, march: 3, april: 4, may: 5, june: 6,
july: 7, august: 8, september: 9, october: 10, november: 11, december: 12,
};
const DINNER_MONTH_NUMBER_TO_NAME = [
'', 'January', 'February', 'March', 'April', 'May', 'June',
'July', 'August', 'September', 'October', 'November', 'December',
];
function isWednesdayNightDinnerMenuQuestion(question) {
const q = normalize(question);
const genericNextDinnerQuestion = (
/^(?:dinner|supper)\s+menu[?!.]*$/.test(q) ||
/^(?:what'?s|what\s+is)\s+for\s+(?:dinner|supper)[?!.]*$/.test(q) ||
/^(?:what'?s|what\s+is)\s+(?:the\s+)?next\s+(?:dinner|supper)\s+menu[?!.]*$/.test(q) ||
/^(?:what\s+is\s+)?(?:the\s+)?next\s+(?:dinner|supper)\s+menu[?!.]*$/.test(q) ||
/^(?:what'?s|what\s+is)\s+(?:the\s+)?(?:dinner|supper)\s+menu[?!.]*$/.test(q) ||
/^(?:what'?s|what\s+is)\s+on\s+the\s+(?:dinner|supper)\s+menu[?!.]*$/.test(q) ||
/^(?:what\s+are\s+we\s+having|what\s+are\s+we\s+eating|what'?s\s+being\s+served|what\s+is\s+being\s+served)\s+for\s+(?:dinner|supper)[?!.]*$/.test(q)
);
if (genericNextDinnerQuestion) return true;

const allKnownDinnerMenusQuestion = (
/\b(all|every)\b[^?!.]{0,30}\b(?:dinner|supper)\s+menus?\b/.test(q) ||
/\b(?:dinner|supper)\s+menus?\b[^?!.]{0,30}\b(all|every)\b/.test(q) ||
/\b(?:list|show|give|give me|can you give me)\b[^?!.]{0,40}\ball\b[^?!.]{0,20}\b(?:dinner|supper)\s+menus?\b/.test(q)
);
const allMenusCompetingContext = /\b(breakfast|lunch|banquet|wedding|funeral|men'?s|women'?s|student|students|youth|kids?|children|conference|retreat)\b/.test(q);
if (allKnownDinnerMenusQuestion && !allMenusCompetingContext) return true;

const tonightMealQuestion = (
/^(?:what\s+are\s+we\s+(?:eating|having)|what'?s\s+being\s+served|what\s+is\s+being\s+served|what\s+are\s+you\s+serving|what'?s\s+on\s+the\s+menu)\s+tonight[?!.]*$/.test(q) ||
/^(?:what'?s|what\s+is)\s+for\s+(?:dinner|supper)\s+tonight[?!.]*$/.test(q) ||
/^(?:what'?s|what\s+is)\s+(?:the\s+)?(?:dinner|supper)\s+menu\s+tonight[?!.]*$/.test(q)
);
if (tonightMealQuestion) return true;

// A menu request with a month/range is assumed to mean the regular Wednesday Night
// Dinner unless the question clearly names another meal, event, or ministry context.
// This restores natural questions such as "What is the menu for the next month?".
const hasMenuRange = /\bmenu\b/.test(q) && (
/\b(this|next|coming)\s+month\b/.test(q) ||
/\b(?:next|coming)\s+(?:30\s+days|4\s+weeks)\b/.test(q) ||
/\b(?:all\s+of|for|during|in)\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\b/.test(q) ||
/\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+menu\b/.test(q)
);
const hasCompetingMealContext = /\b(breakfast|lunch|banquet|wedding|funeral|men'?s|women'?s|student|students|youth|kids?|children|conference|retreat)\b/.test(q);
if (hasMenuRange && !hasCompetingMealContext) return true;
const hasExplicitMenuDate = /\bmenu\b/.test(q) && (
/\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?\b/.test(q) ||
/\b\d{1,2}\/\d{1,2}(?:\/\d{2,4})?\b/.test(q)
);
if (hasExplicitMenuDate && !hasCompetingMealContext) return true;

const asksForFood = /\b(menu|what'?s\s+for\s+(?:dinner|supper)|what\s+is\s+for\s+(?:dinner|supper)|what\s+are\s+we\s+(?:having|eating)|what'?s\s+being\s+served|what\s+is\s+being\s+served|what\s+are\s+you\s+serving|supper)\b/.test(q);
if (!asksForFood) return false;
return (
/\bwednesday\s+night\s+(?:dinner|supper)\b/.test(q) ||
/\bwednesday(?:'s)?\s+(?:dinner|supper)\b/.test(q) ||
/\b(?:dinner|supper)\s+(?:this\s+|next\s+)?wednesday\b/.test(q) ||
/\bmenu\s+(?:for\s+)?(?:this\s+|next\s+)?wednesday\b/.test(q) ||
/\bwhat'?s\s+for\s+(?:dinner|supper)\s+(?:this\s+|next\s+)?wednesday\b/.test(q) ||
/\bwhat\s+are\s+we\s+(?:eating|having)\s+(?:this\s+|next\s+)?wednesday\b/.test(q)
);
}
function dinnerDateKeyFromParts(year, month, day) {
return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}
function dinnerDateKeyToLabel(dateKey) {
const [year, month, day] = String(dateKey || '').split('-').map(Number);
if (!year || !month || !day) return String(dateKey || '');
return `${DINNER_MONTH_NUMBER_TO_NAME[month]} ${day}, ${year}`;
}
function dinnerEventDateKey(record) {
const raw = record?.event_start || record?.starts_at || record?.start_utc || record?.sort_start_utc || '';
const match = String(raw).match(/^(\d{4}-\d{2}-\d{2})/);
return match?.[1] || '';
}
function dinnerEventStartMs(record) {
const raw = record?.event_start || record?.starts_at || record?.sort_start_utc || record?.start_utc || '';
const value = new Date(raw).getTime();
return Number.isFinite(value) ? value : 0;
}
function dinnerMonthStartEnd(year, month) {
const startKey = dinnerDateKeyFromParts(year, month, 1);
const nextMonth = month === 12 ? 1 : month + 1;
const nextYear = month === 12 ? year + 1 : year;
const nextStart = Date.UTC(nextYear, nextMonth - 1, 1);
const end = new Date(nextStart - 24 * 60 * 60 * 1000);
const endKey = dinnerDateKeyFromParts(end.getUTCFullYear(), end.getUTCMonth() + 1, end.getUTCDate());
return { startKey, endKey };
}
function requestedWednesdayDinnerRange(question, nowMs) {
const original = String(question || '');
const q = normalize(original);
const todayKey = nyDateKey(nowMs);
const [todayYear, todayMonth] = todayKey.split('-').map(Number);

// "All dinner menus" means every currently indexed upcoming Wednesday Night Dinner
// occurrence. The live event registry is future-facing, so this remains bounded by the
// events actually present in the index rather than inventing an arbitrary horizon.
if (
  (
    /\b(all|every)\b[^?!.]{0,30}\b(?:dinner|supper)\s+menus?\b/.test(q) ||
    /\b(?:dinner|supper)\s+menus?\b[^?!.]{0,30}\b(all|every)\b/.test(q)
  )
  && !/\b(breakfast|lunch|banquet|wedding|funeral|men'?s|women'?s|student|students|youth|kids?|children|conference|retreat)\b/.test(q)
) {
  return { startKey: todayKey, endKey: '9999-12-31', label: 'all currently listed upcoming dates', type: 'all_upcoming' };
}

// A month name followed by a day is a single-date request, not a month range.
if (/\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?\b/i.test(original)
|| /\b\d{1,2}\/\d{1,2}(?:\/\d{2,4})?\b/.test(original)) {
return null;
}

const namedMonth = original.match(/\b(January|February|March|April|May|June|July|August|September|October|November|December)\b(?:\s+(20\d{2}))?/i);
const namedMonthIsRange = namedMonth && (
/\b(all\s+of|during|in)\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\b/.test(q) ||
/\bmenu\b[^?!.]{0,45}\b(?:for\s+)?(?:all\s+of\s+)?(?:january|february|march|april|may|june|july|august|september|october|november|december)\b/.test(q) ||
/\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b[^?!.]{0,30}\bmenu\b/.test(q)
);
if (namedMonthIsRange) {
const month = DINNER_MONTH_NAME_TO_NUMBER[namedMonth[1].toLowerCase()];
let year = namedMonth[2] ? Number(namedMonth[2]) : todayYear;
if (!namedMonth[2] && month < todayMonth) year += 1;
const { startKey, endKey } = dinnerMonthStartEnd(year, month);
return { startKey, endKey, label: `${DINNER_MONTH_NUMBER_TO_NAME[month]} ${year}`, type: 'month' };
}

if (/\bnext\s+month\b/.test(q) || /\bcoming\s+month\b/.test(q)) {
const month = todayMonth === 12 ? 1 : todayMonth + 1;
const year = todayMonth === 12 ? todayYear + 1 : todayYear;
const { startKey, endKey } = dinnerMonthStartEnd(year, month);
return { startKey, endKey, label: `${DINNER_MONTH_NUMBER_TO_NAME[month]} ${year}`, type: 'month' };
}
if (/\bthis\s+month\b/.test(q)) {
const { startKey, endKey } = dinnerMonthStartEnd(todayYear, todayMonth);
return { startKey, endKey, label: `${DINNER_MONTH_NUMBER_TO_NAME[todayMonth]} ${todayYear}`, type: 'month' };
}
if (/\b(?:next|coming)\s+30\s+days\b/.test(q)) {
return { startKey: todayKey, endKey: addDaysToDateKey(todayKey, 30), label: 'the next 30 days', type: 'window' };
}
if (/\b(?:next|coming)\s+4\s+weeks\b/.test(q)) {
return { startKey: todayKey, endKey: addDaysToDateKey(todayKey, 28), label: 'the next 4 weeks', type: 'window' };
}
return null;
}
function requestedWednesdayDinnerDateSpec(question, nowMs) {
const original = String(question || '');
const q = normalize(original);
const todayKey = nyDateKey(nowMs);
const monthMatch = original.match(/\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b/i);
if (monthMatch) {
return {
month: DINNER_MONTH_NAME_TO_NUMBER[monthMatch[1].toLowerCase()],
day: Number(monthMatch[2]),
year: monthMatch[3] ? Number(monthMatch[3]) : null,
};
}
const numericMatch = original.match(/\b(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?\b/);
if (numericMatch) {
let year = numericMatch[3] ? Number(numericMatch[3]) : null;
if (year !== null && year < 100) year += 2000;
return { month: Number(numericMatch[1]), day: Number(numericMatch[2]), year };
}
if (/\b(today|tonight)\b/.test(q)) return { exactKey: todayKey };
if (/\bthis\s+wednesday\b/.test(q)) {
const weekday = weekdayIndexForDateKey(todayKey);
const daysUntilWednesday = (3 - weekday + 7) % 7;
return { exactKey: addDaysToDateKey(todayKey, daysUntilWednesday) };
}
if (/\bnext\s+wednesday\b/.test(q)) {
const weekday = weekdayIndexForDateKey(todayKey);
let daysUntilWednesday = (3 - weekday + 7) % 7;
if (daysUntilWednesday === 0) daysUntilWednesday = 7;
return { exactKey: addDaysToDateKey(todayKey, daysUntilWednesday) };
}
return null;
}
function dinnerDateKeyMatchesSpec(dateKey, spec) {
if (!dateKey || !spec) return false;
if (spec.exactKey) return dateKey === spec.exactKey;
const [year, month, day] = dateKey.split('-').map(Number);
if (spec.year && year !== spec.year) return false;
return month === spec.month && day === spec.day;
}
function parseWednesdayDinnerMenu(details, targetDateKey) {
const lines = String(details || '').split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
const targetYear = Number(String(targetDateKey || '').slice(0, 4)) || null;
const dateHeadingKey = (line) => {
const match = line.match(/^(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?,?(?:\s+(\d{4}))?$/i);
if (!match) return '';
const year = match[3] ? Number(match[3]) : targetYear;
if (!year) return '';
return dinnerDateKeyFromParts(year, DINNER_MONTH_NAME_TO_NUMBER[match[1].toLowerCase()], Number(match[2]));
};
const firstDateIndex = lines.findIndex((line) => !!dateHeadingKey(line));
const recurringNotes = (firstDateIndex > 0 ? lines.slice(0, firstDateIndex) : [])
.map((line) => line.replace(/^[-*•]\s*/, '').replace(/\s*See\s+below\s+for\s+the\s+weekly\s+menu\.?\s*$/i, '').trim())
.filter(Boolean);
const targetIndex = lines.findIndex((line) => dateHeadingKey(line) === targetDateKey);
if (targetIndex < 0) return { items: [], recurringNotes };
const items = [];
for (let i = targetIndex + 1; i < lines.length; i++) {
if (dateHeadingKey(lines[i])) break;
const item = lines[i].replace(/^[-*•]\s*/, '').trim();
if (item) items.push(item);
}
return { items, recurringNotes };
}
function findWednesdayDinnerMenuForDate(dinnerEvents, eventRecord, targetDateKey) {
const preferredSources = [
eventRecord,
...[...(dinnerEvents || [])].sort((a, b) =>
String(b?.details || b?.content || '').length - String(a?.details || a?.content || '').length
),
].filter(Boolean);
const seen = new Set();
let fallback = { items: [], recurringNotes: [] };
for (const source of preferredSources) {
const key = source.id || source.event_id || source.sort_start_utc || source.event_start || source;
if (seen.has(key)) continue;
seen.add(key);
const parsed = parseWednesdayDinnerMenu(source.details || source.content || '', targetDateKey);
if (parsed.recurringNotes.length > fallback.recurringNotes.length) fallback = parsed;
if (parsed.items.length > 0) return parsed;
}
return fallback;
}
function buildWednesdayDinnerMenuContextRecord(record, menu) {
const targetDateKey = dinnerEventDateKey(record);
const dateLabel = dinnerDateKeyToLabel(targetDateKey);
const lines = [
'Live Planning Center event: Wednesday Night Dinner',
`Event date: ${dateLabel}`,
];
if (record?.event_start) lines.push(`Event start: ${record.event_start}`);
if (record?.event_end) lines.push(`Event end: ${record.event_end}`);
if (record?.location) lines.push(`Location: ${record.location}`);
if (menu.items.length > 0) {
lines.push(`Menu for ${dateLabel}:`);
for (const item of menu.items) lines.push(`- ${item}`);
} else {
lines.push(`No menu for ${dateLabel} is listed in the current live Planning Center details.`);
}
for (const note of menu.recurringNotes) lines.push(`Recurring menu note: ${note}`);
return {
...record,
summary: `Live Wednesday Night Dinner menu lookup for ${dateLabel}.`,
content: lines.join('\n'),
details: lines.join('\n'),
runtime_lookup_type: 'wednesday_dinner_menu',
runtime_menu_date: targetDateKey,
runtime_menu_items: menu.items,
runtime_menu_recurring_notes: menu.recurringNotes,
};
}
function buildWednesdayDinnerMenuRangeRecord(events, entries, range) {
const recurringNotes = [...new Set(entries.flatMap((entry) => entry.recurringNotes || []).map((value) => String(value).trim()).filter(Boolean))];
const lines = [
'Live Planning Center event: Wednesday Night Dinner',
`Requested menu range: ${range.label}`,
];
for (const entry of entries) {
lines.push(`Menu for ${dinnerDateKeyToLabel(entry.dateKey)}:`);
if (entry.items.length > 0) {
for (const item of entry.items) lines.push(`- ${item}`);
} else {
lines.push('- Menu not listed yet.');
}
}
for (const note of recurringNotes) lines.push(`Recurring menu note: ${note}`);
return {
id: `runtime.wednesday_dinner_menu.range.${range.startKey}.${range.endKey}`,
record_type: 'runtime_lookup',
title: `Wednesday Night Dinner menus for ${range.label}`,
summary: `Live Wednesday Night Dinner menus for ${range.label}.`,
content: lines.join('\n'),
details: lines.join('\n'),
priority: 120,
intents: ['calendar', 'event_details', 'menu'],
tags: ['Wednesday Night Dinner', 'menu', 'live lookup', 'date range'],
runtime_lookup_type: 'wednesday_dinner_menu_range',
runtime_menu_range_label: range.label,
runtime_menu_range_type: range.type || null,
runtime_menu_entries: entries.map((entry) => ({ dateKey: entry.dateKey, items: entry.items })),
runtime_menu_recurring_notes: recurringNotes,
runtime_source_event_ids: events.map((event) => event.id).filter(Boolean),
};
}
function buildMissingWednesdayDinnerMenuRecord(targetDateKey = '', rangeLabel = '') {
const dateLabel = rangeLabel || (targetDateKey ? dinnerDateKeyToLabel(targetDateKey) : 'the requested date');
return {
id: `runtime.wednesday_dinner_menu.${targetDateKey || 'upcoming'}`,
record_type: 'runtime_lookup',
title: 'Wednesday Night Dinner menu lookup',
summary: `The current live event index does not contain a Wednesday Night Dinner occurrence for ${dateLabel}.`,
content: `The current live Planning Center event index does not list a Wednesday Night Dinner occurrence for ${dateLabel}. Do not invent a menu for that date.`,
priority: 100,
intents: ['calendar', 'event_details', 'menu'],
tags: ['Wednesday Night Dinner', 'menu', 'live lookup'],
runtime_lookup_type: rangeLabel ? 'wednesday_dinner_menu_range' : 'wednesday_dinner_menu',
runtime_menu_range_label: rangeLabel || null,
runtime_menu_entries: [],
};
}
function buildDeterministicWednesdayDinnerMenuAnswer(record) {
if (!record) return '';
const type = record.runtime_lookup_type;
if (type === 'wednesday_dinner_menu_range') {
const entries = Array.isArray(record.runtime_menu_entries) ? record.runtime_menu_entries : [];
const label = record.runtime_menu_range_label || 'the requested period';
const rangeType = record.runtime_menu_range_type || '';
if (entries.length === 0) {
if (rangeType === 'all_upcoming') return 'No upcoming Wednesday Night Dinner menus are currently published.';
return `No Wednesday Night Dinner occurrences are currently listed for **${label}**.`;
}
const lines = [rangeType === 'all_upcoming'
? 'Here are all currently published Wednesday Night Dinner menus:'
: `Here is the Wednesday Night Dinner menu for **${label}**:`];
for (const entry of entries) {
lines.push('', `### ${dinnerDateKeyToLabel(entry.dateKey)}`);
if (Array.isArray(entry.items) && entry.items.length > 0) {
for (const item of entry.items) lines.push(`- ${item}`);
} else {
lines.push('- Menu not listed yet.');
}
}
const notes = Array.isArray(record.runtime_menu_recurring_notes) ? record.runtime_menu_recurring_notes : [];
if (notes.length > 0) {
lines.push('', '**Also available each week:**');
for (const note of notes) lines.push(`- ${note}`);
}
return lines.join('\n');
}
if (type === 'wednesday_dinner_menu') {
const dateKey = record.runtime_menu_date || '';
const items = Array.isArray(record.runtime_menu_items) ? record.runtime_menu_items : [];
if (!dateKey) return 'No upcoming Wednesday Night Dinner occurrence is currently listed.';
const lines = [`### ${dinnerDateKeyToLabel(dateKey)}`];
if (items.length > 0) {
for (const item of items) lines.push(`- ${item}`);
} else {
lines.push('- Menu not listed yet.');
}
const notes = Array.isArray(record.runtime_menu_recurring_notes) ? record.runtime_menu_recurring_notes : [];
if (notes.length > 0) {
lines.push('', '**Also available each week:**');
for (const note of notes) lines.push(`- ${note}`);
}
return lines.join('\n');
}
return '';
}
function handleWednesdayNightDinnerMenu(all, question, nowMs) {
if (!isWednesdayNightDinnerMenuQuestion(question)) return null;
const dinnerEvents = (all || [])
.filter((record) => record && record.record_type === 'event' && normalize(record.title || '') === WEDNESDAY_DINNER_TITLE && dinnerEventDateKey(record))
.sort((a, b) => dinnerEventStartMs(a) - dinnerEventStartMs(b));

const range = requestedWednesdayDinnerRange(question, nowMs);
if (range) {
const matchingEvents = dinnerEvents.filter((record) => {
const key = dinnerEventDateKey(record);
if (range.type === 'all_upcoming' && dinnerEventStartMs(record) < nowMs - 6 * 60 * 60 * 1000) return false;
return key >= range.startKey && key <= range.endKey;
});
if (matchingEvents.length === 0) {
return { record: buildMissingWednesdayDinnerMenuRecord('', range.label), eventRecords: [], menuFound: false, isRange: true };
}
let entries = matchingEvents.map((event) => {
const dateKey = dinnerEventDateKey(event);
const menu = findWednesdayDinnerMenuForDate(dinnerEvents, event, dateKey);
return { dateKey, items: menu.items, recurringNotes: menu.recurringNotes };
});

// "All menus" means all menus that are actually published right now. Do not
// enumerate future Wednesday Dinner dates whose menu has not been entered yet.
// Explicit month/window requests keep their full requested range so the user can
// still see which requested dates do not yet have a published menu.
let rangeEvents = matchingEvents;
if (range.type === 'all_upcoming') {
const knownDates = new Set(
entries
.filter((entry) => Array.isArray(entry.items) && entry.items.length > 0)
.map((entry) => entry.dateKey)
);
entries = entries.filter((entry) => knownDates.has(entry.dateKey));
rangeEvents = matchingEvents.filter((event) => knownDates.has(dinnerEventDateKey(event)));
}

if (entries.length === 0) {
return {
record: {
...buildMissingWednesdayDinnerMenuRecord('', range.type === 'all_upcoming' ? 'currently published upcoming menus' : range.label),
runtime_menu_range_type: range.type || null,
},
eventRecords: [],
menuFound: false,
isRange: true,
};
}

return {
record: buildWednesdayDinnerMenuRangeRecord(rangeEvents, entries, range),
eventRecords: rangeEvents,
menuFound: entries.some((entry) => entry.items.length > 0),
isRange: true,
};
}

const requested = requestedWednesdayDinnerDateSpec(question, nowMs);
let selected = null;
if (requested) {
const matching = dinnerEvents.filter((record) => dinnerDateKeyMatchesSpec(dinnerEventDateKey(record), requested));
if (matching.length > 0) {
const futureMatching = matching.find((record) => dinnerEventStartMs(record) >= nowMs - 6 * 60 * 60 * 1000);
selected = futureMatching || matching[0];
}
if (!selected) {
const exactKey = requested.exactKey || (requested.year ? dinnerDateKeyFromParts(requested.year, requested.month, requested.day) : '');
return { record: buildMissingWednesdayDinnerMenuRecord(exactKey), eventRecords: [], menuFound: false, isRange: false };
}
} else {
selected = dinnerEvents.find((record) => dinnerEventStartMs(record) >= nowMs - 6 * 60 * 60 * 1000) || null;
if (!selected) return { record: buildMissingWednesdayDinnerMenuRecord(''), eventRecords: [], menuFound: false, isRange: false };
}
const targetDateKey = dinnerEventDateKey(selected);
const menu = findWednesdayDinnerMenuForDate(dinnerEvents, selected, targetDateKey);
return {
record: buildWednesdayDinnerMenuContextRecord(selected, menu),
eventRecords: [selected],
menuFound: menu.items.length > 0,
isRange: false,
};
}

function requestedDateFilter(question, nowMs) {
const nq = normalize(question);
const today = nyDateKey(nowMs);
const makeKeys = (startKey, count) => new Set(Array.from({ length: count }, (_, i) => addDaysToDateKey(startKey, i)));
if (/\btoday\b|\btonight\b/.test(nq)) return { type: 'keys', keys: new Set([today]) };
if (/\btomorrow\b/.test(nq)) return { type: 'keys', keys: new Set([addDaysToDateKey(today, 1)]) };
if (/\bthis\s+weekend\b/.test(nq)) {
const dow = weekdayIndexForDateKey(today);
const daysToSat = (6 - dow + 7) % 7;
const sat = addDaysToDateKey(today, daysToSat);
return { type: 'keys', keys: new Set([sat, addDaysToDateKey(sat, 1)]) };
}
if (/\bthis\s+week\b/.test(nq)) {
const dow = weekdayIndexForDateKey(today);
return { type: 'keys', keys: makeKeys(today, 7 - dow) };
}
if (/\bthis\s+month\b/.test(nq)) return { type: 'month', prefix: today.slice(0, 7) };
if (/\bthis\s+year\b/.test(nq)) return { type: 'year', prefix: today.slice(0, 4) };
return null;
}
function matchesRequestedDate(record, filter) {
if (!filter) return true;
const start = eventStartMs(record);
if (!Number.isFinite(start) || start <= 0) return false;
const key = nyDateKey(start);
if (filter.type === 'keys') return filter.keys.has(key);
return key.startsWith(filter.prefix);
}
function eventSpecificQueryTokens(question) {
return tokenize(question).filter((token) => token.length >= 3 && !EVENT_QUERY_STOPWORDS.has(token));
}
function removeDetectedMinistryTokens(tokens, ministries) {
if (ministries.length === 0) return tokens;
const ministryTokens = new Set();
for (const ministry of ministries) {
const canon = canonMinistry(ministry);
for (const variant of MINISTRY_CANON[canon] || []) {
for (const token of tokenize(variant)) ministryTokens.add(token.replace(/'/g, ''));
}
}
return tokens.filter((token) => !ministryTokens.has(token.replace(/'/g, '')));
}
function eventMatchesSpecificQuery(record, queryTokens) {
if (queryTokens.length === 0) return true;
const fields = [record.title || '', ...(record.activity_aliases || []), ...(record.search_terms || []), ...(record.tags || [])];
const candidateTokens = new Set(fields.flatMap((value) => tokenize(value)));
for (const token of queryTokens) {
if (candidateTokens.has(token)) return true;
if (token.length >= 5) {
for (const candidate of candidateTokens) {
if (candidate.length >= 5 && editDistance(token, candidate) <= 1) return true;
}
}
}
return false;
}
// Upcoming-event handler: inspects ALL future event records from the full record
// list (not truncated), filters by normalized ministry aliases, then sorts
// relevant matches chronologically. Relevance first, chronology second.
function handleCalendar(all, question, intents, ministries, nowMs) {
const wantsSmallGroup = intents.includes('small_group');
const isUpcoming = isUpcomingEventQuestion(question);
if (!wantsSmallGroup && !isUpcoming) return null;
const targetType = wantsSmallGroup ? 'small_group' : 'event';
const dateFilter = requestedDateFilter(question, nowMs);
let candidates = all.filter((record) => {
if (record.record_type !== targetType) return false;
const end = record.sort_end_utc || record.end_utc || record.ends_at;
if (end && new Date(end).getTime() < nowMs) return false;
return matchesRequestedDate(record, dateFilter);
});
if (ministries.length > 0) {
candidates = candidates.filter((record) => {
const titleNorm = normalizeMinistryToken(record.title || '');
const recMinCanon = (record.ministries || []).map(canonMinistry);
for (const ministry of ministries) {
const canon = canonMinistry(ministry);
const variants = [...new Set((MINISTRY_CANON[canon] || []).map(normalizeMinistryToken))];
if (variants.some((variant) => new RegExp(`\b${variant}\b`).test(titleNorm))) return true;
if (recMinCanon.length === 1 && recMinCanon[0] === canon) return true;
}
return false;
});
}
if (!wantsSmallGroup) {
const specificTokens = removeDetectedMinistryTokens(eventSpecificQueryTokens(question), ministries);
if (specificTokens.length > 0) {
const relevant = candidates.filter((record) => eventMatchesSpecificQuery(record, specificTokens));
if (relevant.length > 0) candidates = relevant;
}
}
candidates.sort((a, b) => eventStartMs(a) - eventStartMs(b));
if (candidates.length === 0) return [];
return isSingularRequest(question) ? candidates.slice(0, 1) : candidates.slice(0, 8);
}
function formatNyEventDate(ms) {
if (!Number.isFinite(ms)) return '';
return new Intl.DateTimeFormat('en-US', {
timeZone: 'America/New_York',
month: 'long',
day: 'numeric',
}).format(new Date(ms));
}
function formatNyEventTime(ms) {
if (!Number.isFinite(ms)) return '';
return new Intl.DateTimeFormat('en-US', {
timeZone: 'America/New_York',
hour: 'numeric',
minute: '2-digit',
}).format(new Date(ms));
}
function eventEndMs(record) {
const raw = record?.sort_end_utc || record?.event_end || record?.end_utc || record?.ends_at;
if (!raw) return NaN;
const value = new Date(raw).getTime();
return Number.isFinite(value) ? value : NaN;
}
function eventLocationText(record) {
return String(record?.location || '').trim();
}
function selectViewAllEventsLink(index) {
const links = (index?.records || []).filter((record) => record && record.record_type === 'action_link');
const exact = links.find((record) => normalize(record.title || '') === 'view all events');
if (exact?.url) return exact;
return links.find((record) => {
const title = normalize(record.title || '');
const url = String(record.url || '');
return title.includes('events') && /urbancrest\.church\/events(?:$|[/?#])/i.test(url);
}) || null;
}
function buildDeterministicUpcomingEventsAnswer(records, viewAllLink = null) {
const sorted = [...records].sort((a, b) => eventStartMs(a) - eventStartMs(b));
if (sorted.length === 0) return '';
const groups = [];
let currentDate = '';
let currentItems = [];
for (const record of sorted) {
const startMs = eventStartMs(record);
if (!Number.isFinite(startMs)) continue;
const dateLabel = formatNyEventDate(startMs);
if (!dateLabel) continue;
if (dateLabel !== currentDate) {
if (currentItems.length) groups.push({ date: currentDate, items: currentItems });
currentDate = dateLabel;
currentItems = [];
}
const startTime = formatNyEventTime(startMs);
const endMs = eventEndMs(record);
let timeText = startTime;
if (Number.isFinite(endMs) && endMs > startMs && nyDateKey(endMs) === nyDateKey(startMs)) {
timeText = `${startTime} – ${formatNyEventTime(endMs)}`;
}
const location = eventLocationText(record);
const title = String(record.title || 'Untitled Event').trim();
let item = `- **${title}**`;
if (timeText) item += `: ${timeText}`;
if (location) item += ` at ${location}`;
currentItems.push(item);
}
if (currentItems.length) groups.push({ date: currentDate, items: currentItems });
const lines = [
'Here’s what is coming up at Urbancrest:',
'',
];
for (const group of groups) {
lines.push(`### ${group.date}`, '', ...group.items, '');
}
if (viewAllLink?.url) {
lines.push(`[View All Events](${viewAllLink.url})`);
}
return lines.join('\n').trim();
}


function friendlyPublicUrlLabel(rawUrl) {
const value = String(rawUrl || '').trim();
if (!value) return 'Learn More';
try {
  const url = new URL(value);
  const host = normalize(url.hostname).replace(/^www\./, '');
  const path = url.pathname.replace(/\/+$/, '');
  const slug = path.split('/').filter(Boolean).pop() || '';
  const known = {
    'stephen-ministry': 'Stephen Ministry page',
    'events': 'Urbancrest Events',
    'plan-your-visit': 'Plan Your Visit',
    'students': 'Student Ministry page',
    'kids': 'Kids Ministry page',
    'men': "Men's Ministry page",
    'women': "Women's Ministry page",
    'missions': 'Missions page',
    'small-groups': 'Small Groups page',
  };
  if (host === 'urbancrest.church' && known[slug]) return known[slug];
  if (host === 'stephenministries.org') return 'Stephen Ministries';
  if (slug) {
    return slug
      .split(/[-_]+/)
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');
  }
  return url.hostname.replace(/^www\./, '');
} catch {
  return 'Learn More';
}
}

function linkifyBarePublicUrls(text) {
const source = String(text || '');
if (!source) return source;
// Direct ministry answers bypass the LLM, so raw URLs in otherwise public article
// prose must be converted to Markdown here. URLs already used as Markdown link
// destinations are left unchanged.
return source.replace(/(?<!\]\()https?:\/\/[^\s)>]+/g, (rawMatch) => {
  let rawUrl = rawMatch;
  let punctuation = '';
  while (/[.,;:!?]$/.test(rawUrl)) {
    punctuation = rawUrl.slice(-1) + punctuation;
    rawUrl = rawUrl.slice(0, -1);
  }
  const label = friendlyPublicUrlLabel(rawUrl);
  return `[${label}](${rawUrl})${punctuation}`;
});
}

function publicMinistryOverviewBody(record) {
if (!record) return '';
const content = String(record.content || '').trim();
if (!content) return String(record.summary || '').trim();

const lines = content.split('\n');
const kept = [];
let skipSection = false;
for (const rawLine of lines) {
  const line = rawLine.trimEnd();
  const heading = line.match(/^#{1,6}\s+(.+)$/);
  if (heading) {
    const headingText = normalize(heading[1]);
    // These headings contain repository/editorial metadata or a static next step.
    // The runtime supplies live event enrichment and approved action links separately.
    if (headingText === 'urbancrest information' || headingText === 'next step' ||
        ((record.leadership_status === 'vacant' || record.leadership_status === 'transitional') && headingText === 'current leadership')) {
      skipSection = true;
      continue;
    }
    // The H1 repeats the record title. Short/Detailed are structural labels, not useful
    // to a visitor. Preserve other genuine public subheadings.
    if (line.startsWith('# ') || headingText === 'short answer' || headingText === 'detailed answer') {
      skipSection = false;
      continue;
    }
    skipSection = false;
    kept.push(line);
    continue;
  }
  if (skipSection) continue;
  const normalizedLine = normalize(line);
  if (!normalizedLine) {
    kept.push('');
    continue;
  }
  // Keep repository/editorial language out of public answers.
  if (normalizedLine.includes('current schedules, age ranges, locations, and event details should come from verified urbancrest sources')) continue;
  if (normalizedLine.includes('this article intentionally avoids unverified schedules or contact details')) continue;
  if (normalizedLine.includes('should not be described') || normalizedLine.includes('do not describe')) continue;
  if (/^for current (events|event|dates|opportunities|tournament dates)/i.test(line) && /urbancrest events/i.test(line)) continue;
  kept.push(line);
}

let body = kept.join('\n').replace(/\n{3,}/g, '\n\n').trim();
if (!body) body = String(record.summary || '').trim();
return linkifyBarePublicUrls(body);
}

function ministryOverviewEventKeys(record, question) {
const keys = new Set();

// The user's requested ministry is the strongest authority for enrichment.
for (const value of detectMinistries(question)) {
  const key = canonMinistry(value);
  if (Object.prototype.hasOwnProperty.call(MINISTRY_CANON, key)) keys.add(key);
}

// Add only explicit canonical ministry ownership from the overview record.
// Do NOT derive event filters from overview tags, audiences, prose, or generic words
// such as "families". Those are retrieval metadata, not event ownership.
for (const value of (record?.ministries || [])) {
  const key = canonMinistry(value);
  if (Object.prototype.hasOwnProperty.call(MINISTRY_CANON, key)) keys.add(key);
}

return [...keys].filter(Boolean);
}
function ministryEventSeriesKey(record) {
const candidates = [
  ...(record?.activity_aliases || []),
  ...(record?.event_aliases || []),
  record?.title || '',
]
  .map((value) => normalizeMinistryToken(value)
    .replace(/^urbancrest\s+/, '')
    .replace(/\b20\d{2}\b/g, '')
    .replace(/\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?\b/g, '')
    .replace(/\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b/g, '')
    .replace(/\s+/g, ' ')
    .trim())
  .filter(Boolean);
if (!candidates.length) return normalizeMinistryToken(record?.id || '');
// Prefer the shortest normalized alias. This collapses pairs such as
// "Urbancrest Women's Conference" and "Women's Conference" into one series.
candidates.sort((a, b) => a.length - b.length || a.localeCompare(b));
return candidates[0];
}
function eventIsPublicForMinistryEnrichment(record) {
if (!record || record.record_type !== 'event') return false;
if (record.hidden === true) return false;
if (record.publicly_listed === false || record.publiclyListed === false) return false;
const status = normalize(record.status || '');
if (['hidden', 'private', 'draft', 'link only', 'link_only'].includes(status)) return false;
return true;
}

function selectUpcomingMinistryEvents(all, overviewRecord, question, nowMs, limit = 3) {
const keys = ministryOverviewEventKeys(overviewRecord, question);
if (keys.length === 0) return [];

const candidates = [];
for (const record of (all || [])) {
  if (!eventIsPublicForMinistryEnrichment(record)) continue;
  const start = eventStartMs(record);
  const end = eventEndMs(record);
  if (!Number.isFinite(start)) continue;
  if (Number.isFinite(end) ? end < nowMs : start < nowMs) continue;
  const matchScore = Math.max(...keys.map((key) => ministryEventMatchScore(key, record, overviewRecord)), 0);
  if (matchScore < 145) continue;
  candidates.push({ record, matchScore });
}

// Keep the earliest future occurrence of the same recurring/named event so a weekly
// series cannot consume the whole enrichment block.
candidates.sort((a, b) => eventStartMs(a.record) - eventStartMs(b.record) || b.matchScore - a.matchScore);
const unique = [];
const seen = new Set();
for (const item of candidates) {
  const record = item.record;
  const seriesKey = ministryEventSeriesKey(record) || String(record.id || '');
  if (seen.has(seriesKey)) continue;
  seen.add(seriesKey);
  unique.push(record);
  if (unique.length >= limit) break;
}
return unique;
}

function formatMinistryEnrichmentDate(ms) {
if (!Number.isFinite(ms)) return '';
return new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  weekday: 'long',
  month: 'long',
  day: 'numeric',
}).format(new Date(ms));
}

function buildMinistryEventBullet(record) {
const startMs = eventStartMs(record);
if (!Number.isFinite(startMs)) return '';
const title = String(record.title || 'Upcoming Event').trim();
const date = formatMinistryEnrichmentDate(startMs);
const allDay = record.all_day === true || record.allDay === true;
let when = date;
if (!allDay) {
  const startTime = formatNyEventTime(startMs);
  const endMs = eventEndMs(record);
  let time = startTime;
  if (Number.isFinite(endMs) && endMs > startMs && nyDateKey(endMs) === nyDateKey(startMs)) {
    time = `${startTime} – ${formatNyEventTime(endMs)}`;
  }
  if (time) when += ` at ${time}`;
}
const location = eventLocationText(record);
let line = `- **${title}**: ${when}`;
if (location) line += ` at ${location}`;

// Church Center remains the transactional layer. Only expose the exact registration
// action when the event record explicitly says registration is available.
const registrationAvailable = record.registration_available === true || record.registrationAvailable === true;
const registrationUrl = String(record.registration_url || record.registrationUrl || '').trim();
if (registrationAvailable && registrationUrl) line += ` · [Register](${registrationUrl})`;
return line;
}

function buildDeterministicMinistryOverviewAnswer(overviewRecord, upcomingEvents = [], viewAllLink = null) {
const body = publicMinistryOverviewBody(overviewRecord);
const lines = [];
if (body) lines.push(body);
else if (overviewRecord?.summary) lines.push(String(overviewRecord.summary).trim());

if (upcomingEvents.length > 0) {
  lines.push('', '### Upcoming events', '');
  for (const event of upcomingEvents) {
    const bullet = buildMinistryEventBullet(event);
    if (bullet) lines.push(bullet);
  }
}
const recordPointsToEvents = (overviewRecord?.resources || []).some((value) => normalize(value).includes('events'));
if (viewAllLink?.url && (upcomingEvents.length > 0 || recordPointsToEvents)) {
  lines.push('', `[View All Events](${viewAllLink.url})`);
}
return lines.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

function isGenericServiceTimesQuestion(question, intents) {
return intents.includes('service_times') && !isDateSpecific(question);
}

function normalizeServiceTimeLabel(raw) {
const match = String(raw || '').trim().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
if (!match) return '';
return `${Number(match[1])}:${match[2]} ${match[3].toUpperCase()}`;
}

function extractRegularSundayServiceTimes(records) {
// The runtime config explicitly says not to hardcode service times in application logic.
// Read them from the authoritative service-time records instead.
const preferredIds = [
'about.services.times',
'schedule.worship.sunday',
'schedule.ministry.worship',
'schedule.weekly',
];
const ordered = [];
for (const id of preferredIds) {
const record = records.find((r) => r?.id === id);
if (record) ordered.push(record);
}
for (const record of records) {
if (record && !ordered.some((item) => item.id === record.id)) ordered.push(record);
}
for (const record of ordered) {
const text = [record.summary, record.content, record.answer_guidance]
.filter(Boolean)
.join(' ');
const matches = text.match(/\b(?:1[0-2]|0?[1-9]):[0-5]\d\s*(?:AM|PM)\b/gi) || [];
const unique = [];
const seen = new Set();
for (const raw of matches) {
const value = normalizeServiceTimeLabel(raw);
if (value && !seen.has(value)) {
seen.add(value);
unique.push(value);
}
}
// The concise authoritative Sunday service article begins with the two Sunday times.
if (unique.length >= 2) return unique.slice(0, 2);
}
return [];
}

function buildDeterministicRegularServiceTimesAnswer(records, planVisitLink = null) {
const times = extractRegularSundayServiceTimes(records);
if (times.length < 2) return '';
const lines = [
`We'd love to have you join us this Sunday! Worship services at Urbancrest are at **${times[0]}** and **${times[1]}**.`,
];
if (planVisitLink?.url) {
lines.push('', `If you're new to Urbancrest, the [${planVisitLink.title || 'Plan Your Visit'}](${planVisitLink.url}) page has everything you need to get started.`);
}
return lines.join('\n');
}

function buildDeterministicDirectionsAnswer(actionLinks = []) {
const lines = [
`We'd love to have you visit! Urbancrest is located at **2634 Drake Road, Lebanon, Ohio 45036**.`,
];

const google = actionLinks.find((link) => /google/i.test(`${link?.title || ''} ${link?.url || ''}`));
const apple = actionLinks.find((link) => /apple/i.test(`${link?.title || ''} ${link?.url || ''}`));
const mapLinks = [];
if (google?.url) mapLinks.push(`[Google Maps](${google.url})`);
if (apple?.url) mapLinks.push(`[Apple Maps](${apple.url})`);

if (mapLinks.length > 0) {
lines.push('', `For turn-by-turn directions, use ${mapLinks.join(' or ')}.`);
}

return lines.join('\n');
}

// Named-event lookup handles direct questions about a specific live event even when
// the user does not use temporal words such as "upcoming" or "next". This is also
// intentionally evaluated before recurring-schedule routing so "When is Engage?"
// resolves to the dated event instead of being mistaken for a weekly schedule.
const NAMED_EVENT_REQUEST_WORDS = new Set([
...EVENT_QUERY_STOPWORDS,
'register', 'registration', 'rsvp', 'signup', 'sign', 'cost', 'price', 'much',
'detail', 'details', 'information', 'info', 'ticket', 'tickets', 'attend', 'attending',
'open', 'closed', 'full', 'available', 'availability', 'date', 'time', 'location',
'conference', 'class', 'service', 'festival', 'fest', 'retreat', 'breakfast', 'lunch',
'dinner', 'party', 'outreach',
]);
const GENERIC_SINGLE_EVENT_ALIASES = new Set([
'event', 'activity', 'conference', 'class', 'service', 'festival', 'fest', 'retreat',
'breakfast', 'lunch', 'dinner', 'party', 'outreach', 'meeting', 'gathering', 'worship',
]);
function namedEventQueryTokens(question) {
return tokenize(question).filter((token) => token.length >= 3 && !NAMED_EVENT_REQUEST_WORDS.has(token));
}
function tokenMatchesCandidate(token, candidates) {
if (candidates.has(token)) return true;
if (token.length < 5) return false;
for (const candidate of candidates) {
if (candidate.length >= 5 && editDistance(token, candidate) <= 1) return true;
}
return false;
}
function handleNamedEvent(all, question, nowMs) {
const dinnerMenuLookup = handleWednesdayNightDinnerMenu(all, question, nowMs);
if (dinnerMenuLookup) return dinnerMenuLookup.record;
const nq = normalize(question);
const queryTokens = namedEventQueryTokens(question);
if (queryTokens.length === 0) return null;

const scored = [];
for (const record of all) {
if (!record || record.record_type !== 'event') continue;
if (record.routine_schedule_occurrence === true) continue;
const end = record.sort_end_utc || record.event_end || record.end_utc || record.ends_at;
if (end && new Date(end).getTime() < nowMs) continue;

const aliases = [
record.title || '',
...(record.activity_aliases || []),
...(record.event_aliases || []),
].map(normalize).filter((value) => value && value.length >= 3);
if (aliases.length === 0) continue;

let exactAlias = false;
let bestAliasTokenMatches = 0;
for (const alias of aliases) {
const aliasTokens = tokenize(alias);
const genericSingle = aliasTokens.length === 1 && GENERIC_SINGLE_EVENT_ALIASES.has(aliasTokens[0]);
if (!genericSingle && nq.includes(alias)) exactAlias = true;
const aliasTokenSet = new Set(aliasTokens);
let matches = 0;
for (const token of queryTokens) {
if (tokenMatchesCandidate(token, aliasTokenSet)) matches++;
}
bestAliasTokenMatches = Math.max(bestAliasTokenMatches, matches);
}

const contentTokenSet = new Set(tokenize(`${record.title || ''} ${record.summary || ''} ${record.content || ''} ${record.details || ''}`));
let contentMatches = 0;
for (const token of queryTokens) {
if (tokenMatchesCandidate(token, contentTokenSet)) contentMatches++;
}

const allAliasTokensMatched = bestAliasTokenMatches === queryTokens.length;
const strongContentMatch = queryTokens.length >= 2 && contentMatches === queryTokens.length;
if (!(exactAlias || allAliasTokensMatched || strongContentMatch)) continue;

let score = 0;
if (exactAlias) score += 600;
score += bestAliasTokenMatches * 150;
if (strongContentMatch) score += 220;
if (record.registration_url) score += 35;
if (record.event_source === 'planning_center_registrations_api' || (record.event_sources || []).includes('planning_center_registrations_api')) score += 20;
score += (record.priority || 0) / 10;
scored.push({ record, score });
}

scored.sort((a, b) => b.score - a.score || eventStartMs(a.record) - eventStartMs(b.record));
return scored.length > 0 ? scored[0].record : null;
}
// Conservative typo tolerance: Levenshtein distance, capped at 1 for tokens >= 5 chars.
function editDistance(a, b) {
if (a === b) return 0;
const la = a.length;
const lb = b.length;
if (Math.abs(la - lb) > 1) return 2;
if (la === 0) return lb;
if (lb === 0) return la;
let prev = new Array(lb + 1);
let curr = new Array(lb + 1);
for (let j = 0; j <= lb; j++) prev[j] = j;
for (let i = 1; i <= la; i++) {
curr[0] = i;
for (let j = 1; j <= lb; j++) {
const cost = a.charCodeAt(i - 1) === b.charCodeAt(j - 1) ? 0 : 1;
curr[j] = Math.min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost);
}
[prev, curr] = [curr, prev];
}
return prev[lb];
}
// Match query tokens (>=5 chars, edit distance <=1) against title, activity aliases,
// search terms, and (optionally) tags. Returns the matched query tokens.
function activityMatchedTokens(record, queryTokens, includeTags) {
const candidateTokens = new Set();
const push = (text) => { for (const t of tokenize(text || '')) candidateTokens.add(t); };
push(record.title || '');
(record.activity_aliases || []).forEach(push);
(record.schedule_aliases || []).forEach(push);
(record.ministry_aliases || []).forEach(push);
(record.search_terms || []).forEach(push);
if (includeTags) (record.tags || []).forEach(push);
const matched = [];
for (const t of queryTokens) {
if (t.length < 5) continue;
if (candidateTokens.has(t)) { matched.push(t); continue; }
let fuzzy = false;
for (const c of candidateTokens) {
if (c.length >= 5 && editDistance(t, c) <= 1) { fuzzy = true; break; }
}
if (fuzzy) matched.push(t);
}
return matched;
}
// Activity-availability questions ("Does Urbancrest have pickleball?") search BOTH
// recurring schedule records and future event records. If a matching schedule exists,
// it serves as evidence the activity is regularly offered. Otherwise, fall back to
// future event occurrences. Recurring event occurrences are deduped (group_id, else
// normalized title) and the earliest future match is kept for singular requests.
function handleActivityAvailability(scored, question, intents, nowMs) {
if (!isActivityAvailabilityQuestion(question, intents)) return null;
const queryTokens = tokenize(question).filter((t) => !STOPWORDS.has(t) && t.length >= 5);
if (queryTokens.length === 0) return null;
// 1. Search recurring schedule records first
const scheduleMatches = scored.filter((s) => {
const r = s.record;
if (r.record_type !== 'schedule') return false;
return activityMatchedTokens(r, queryTokens, true).length > 0;
});
// 2. Search future event records
const eventCandidates = scored.filter((s) => {
const r = s.record;
if (r.record_type !== 'event') return false;
const end = r.sort_end_utc || r.end_utc || r.ends_at;
if (end && new Date(end).getTime() < nowMs) return false;
return activityMatchedTokens(r, queryTokens, false).length > 0;
});
if (scheduleMatches.length === 0 && eventCandidates.length === 0) return null;
// If a matching schedule exists, use it as evidence the activity is regularly offered
if (scheduleMatches.length > 0) {
scheduleMatches.sort((a, b) => b.score - a.score);
const scheduleRecords = scheduleMatches.slice(0, 4).map((s) => s.record);
// Also include upcoming event occurrences for dates/times
if (eventCandidates.length > 0) {
const startOf = (r) => new Date(r.sort_start_utc || r.start_utc || r.starts_at || 0).getTime();
const sorted = [...eventCandidates].sort((a, b) => startOf(a.record) - startOf(b.record));
const deduped = new Map();
for (const s of sorted) {
const r = s.record;
const key = r.group_id || normalize(r.title || '') || r.id;
if (!deduped.has(key)) deduped.set(key, s.record);
}
const eventRecords = [...deduped.values()].slice(0, 4);
const seen = new Set(scheduleRecords.map((r) => r.id));
const records = [...scheduleRecords];
for (const r of eventRecords) {
if (!seen.has(r.id)) { records.push(r); seen.add(r.id); }
if (records.length >= 8) break;
}
return records;
}
return scheduleRecords;
}
// No schedule match - use events only
const startOf = (r) => new Date(r.sort_start_utc || r.start_utc || r.starts_at || 0).getTime();
const singular = isSingularRequest(question);
if (singular) {
const groups = new Map();
for (const s of eventCandidates) {
const r = s.record;
const key = r.group_id || normalize(r.title || '') || r.id;
const start = startOf(r);
const existing = groups.get(key);
if (!existing || start < existing.start) groups.set(key, { record: r, start });
}
return [...groups.values()].sort((a, b) => a.start - b.start).slice(0, 3).map((g) => g.record);
}
const sorted = [...eventCandidates].sort((a, b) => startOf(a.record) - startOf(b.record));
return sorted.slice(0, 8).map((s) => s.record);
}
// Activity-availability applies only to questions asking whether an activity exists
// or is offered. It must NOT fire merely because "when", "meet", "ministry", or
// "schedule" appears.
function isActivityAvailabilityQuestion(question, intents) {
if (intents.includes('activity_availability')) return true;
const nq = normalize(question);
return /\b(does\s+(urbancrest|your church|the church)\s+have|do\s+you\s+have|do\s+you\s+offer|does\s+urbancrest\s+offer|is\s+there|are\s+there|can\s+i\s+play|can\s+we\s+play|can\s+i\s+participate|do\s+you\s+host|does\s+urbancrest\s+host)\b/.test(nq);
}
// Ministry keywords mapped to the canonical ministry key used in knowledge records.
const MINISTRY_KEYS = [
['students', ['student', 'students', 'youth', 'teen', 'teens', 'teenager', 'teenagers', 'middle school', 'high school']],
['children', ['children', 'child', 'kids', 'kid', "children's"]],
['men', ['men', "men's", 'mens']],
['women', ['women', "women's", 'womens']],
['worship', ['worship']],
['missions', ['mission', 'missions', 'missional']],
['preschool', ['preschool']],
['nursery', ['nursery']],
['senior', ['senior', 'seniors']],
['family', ['family', 'families']],
['local_missions', ['local missions', 'local mission', 'local outreach', 'community outreach', 'serving lebanon', 'serve the community']],
];
function detectMinistryKey(question) {
const nq = ' ' + normalize(question) + ' ';
for (const [key, words] of MINISTRY_KEYS) {
if (words.some((w) => new RegExp('\\b' + w.replace(/['’]/g, "['’]?") + '\\b').test(nq))) return key;
}
return null;
}
// Detect generic schedule questions: "when does X meet", "what time does X meet",
// "what is the X schedule", "what days does X meet", "what time is X", "when is X".
// Temporal questions ("when is the next event") are excluded - those are calendar questions.
function detectScheduleContext(question, intents) {
const nq = normalize(question);
const temporal = isTemporal(question);
const hasMeet = /\b(meet|meets|meeting|meetings|service|services|worship)\b/.test(nq);
const hasScheduleWord = /\bschedule\b/.test(nq);
const hasWhen = /\b(when|what\s+time|what\s+days)\b/.test(nq);
const hasWhenIs = /\bwhen\s+is\b/.test(nq);
const hasWhatTimeIs = /\bwhat\s+time\s+is\b/.test(nq);
const isCalendar = intents.includes('calendar');
// "when does X meet" / "what time does X meet" / "what days does X meet" - not temporal
if (!temporal && hasWhen && hasMeet) {
return { isScheduleQ: true, ministry: detectMinistryKey(question), isServiceTimes: intents.includes('service_times') };
}
// "what is the X schedule"
if (hasScheduleWord) {
return { isScheduleQ: true, ministry: detectMinistryKey(question), isServiceTimes: intents.includes('service_times') };
}
// "what time is X" / "when is X" - not temporal, not a calendar question
if (!temporal && !isCalendar && (hasWhatTimeIs || hasWhenIs)) {
return { isScheduleQ: true, ministry: detectMinistryKey(question), isServiceTimes: intents.includes('service_times') };
}
return { isScheduleQ: false, ministry: null, isServiceTimes: false };
}
// Generic schedule handler: matches aliases to find the right schedule record(s).
// Uses schedule_aliases, ministry_aliases, search_terms, title, tags, and ministries
// for matching, with the same conservative typo tolerance as activity retrieval.
// Prefers ministry aggregate records for broad ministry questions, specific activity
// records for named activities. Staff key comes from recommended_contact_staff_key
// when show_staff_card_on_schedule_queries is true - no retrieval slot spent on staff routes.
function handleSchedule(all, scored, scheduleCtx, question, nowMs) {
if (!scheduleCtx.isScheduleQ) return null;
const normQ = normalize(question);
const queryTokens = tokenize(question).filter((t) => !STOPWORDS.has(t) && t.length >= 3);
// Find schedule records that match the query
const scheduleScored = scored.filter((s) => s.record.record_type === 'schedule');
if (scheduleScored.length === 0) return null;
const matched = scheduleScored.filter((s) => {
const r = s.record;
// Exact alias phrase match
const aliases = [
...(r.schedule_aliases || []),
...(r.ministry_aliases || []),
...(r.search_terms || []),
].map(normalize).filter((a) => a && a.length >= 3);
for (const alias of aliases) {
if (normQ.includes(alias)) return true;
}
// Title match
const title = normalize(r.title || '');
if (title && title.length >= 3 && (normQ.includes(title) || title.includes(normQ))) return true;
// Fuzzy token match (same conservative typo tolerance as activity retrieval)
if (activityMatchedTokens(r, queryTokens, true).length > 0) return true;
// Ministry match
if (scheduleCtx.ministry) {
const recMin = (r.ministries || []).map(normalize);
if (recMin.includes(scheduleCtx.ministry)) return true;
}
return false;
});
if (matched.length === 0) return null;
if (scheduleCtx.isServiceTimes) {
const serviceIds = new Set(['schedule.worship.sunday', 'schedule.ministry.worship', 'schedule.weekly']);
const serviceMatched = matched.filter((item) => serviceIds.has(item.record.id));
if (serviceMatched.length > 0) {
matched.length = 0;
matched.push(...serviceMatched);
}
}
// Determine if the question names a specific activity (not just a broad ministry)
const hasNamedActivity = matched.some((s) => {
const r = s.record;
if (r.schedule_scope === 'ministry' || (r.id || '').startsWith('schedule.ministry.')) return false;
const aliases = [...(r.schedule_aliases || []), ...(r.ministry_aliases || [])].map(normalize);
return aliases.some((a) => a && a.length >= 3 && normQ.includes(a));
});
// Sort: scope preference + score
matched.sort((a, b) => {
const aAgg = (a.record.schedule_scope === 'ministry' || (a.record.id || '').startsWith('schedule.ministry.')) ? 1 : 0;
const bAgg = (b.record.schedule_scope === 'ministry' || (b.record.id || '').startsWith('schedule.ministry.')) ? 1 : 0;
if (scheduleCtx.ministry) {
if (hasNamedActivity) {
// Named activity: prefer specific (non-aggregate) records
if (aAgg !== bAgg) return aAgg - bAgg;
} else {
// Broad ministry: prefer aggregate records
if (aAgg !== bAgg) return bAgg - aAgg;
}
}
return b.score - a.score;
});
const records = matched.slice(0, 8).map((s) => s.record);
// Staff key from the top schedule record's recommended_contact_staff_key
let staffKey = null;
const topRecord = records[0];
if (topRecord && topRecord.show_staff_card_on_schedule_queries === true && topRecord.recommended_contact_staff_key) {
staffKey = topRecord.recommended_contact_staff_key;
}
return { records, staffKey, isServiceTimes: scheduleCtx.isServiceTimes };
}
function isDateSpecific(q) {
const nq = normalize(q);
if (DATE_REFERENCE_PHRASES.some((p) => nq.includes(p))) return true;
if (HOLIDAY_PHRASES.some((p) => nq.includes(p))) return true;
if (/\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\b/.test(nq)) return true;
if (/\b\d{1,2}\/\d{1,2}(\/\d{2,4})?\b/.test(nq)) return true;
return false;
}
function recordExcludedForServiceTimes(r) {
if ((r.record_type || '') !== 'event') return false;
const ex = (r.retrieval_exclude_for_intents || []).map(normalize);
return ex.includes('service_times');
}
// Service-time questions have a canonical answer (9:30 AM & 11:00 AM Sundays) backed by
// authoritative records. Routine Sunday service event occurrences are calendar instances of
// that schedule, not competing definitions, so they never lower confidence.
function handleServiceTimes(all, scored, question, intents, nowMs) {
if (!intents.includes('service_times')) return null;
const auth = scored.filter((s) => {
const af = (s.record.authoritative_for || []).map(normalize);
return af.some((a) => SERVICE_TIME_AUTH.has(a));
});
const preferred = scored.filter((s) => SERVICE_TIME_PREFERRED_IDS.has(s.record.id));
let candidates = [...auth, ...preferred].filter((s) => !recordExcludedForServiceTimes(s.record));
const seen = new Set();
candidates = candidates.filter((s) => {
if (seen.has(s.record.id)) return false;
seen.add(s.record.id);
return true;
});
// Date-specific requests: search live event records for a dated schedule exception.
// The exception is used only when explicitly present; otherwise the regular Sunday schedule applies.
const dateSpecific = isDateSpecific(question);
let exceptionRecords = [];
if (dateSpecific) {
const horizon = nowMs + 21 * 24 * 3600 * 1000;
exceptionRecords = all.filter((r) => {
if ((r.record_type || '') !== 'event') return false;
if (recordExcludedForServiceTimes(r)) return false;
const start = new Date(r.sort_start_utc || r.start_utc || r.starts_at || 0).getTime();
if (!start || start < nowMs - 24 * 3600 * 1000 || start > horizon) return false;
const title = normalize(r.title || '');
const tags = (r.tags || []).map(normalize);
const isServiceLike = /service|worship|sunday|schedule change|no service|combined service|special service|time change/.test(title)
|| tags.some((t) => /service|worship|schedule/.test(t));
return isServiceLike;
});
exceptionRecords.sort((a, b) => {
const aS = new Date(a.sort_start_utc || a.start_utc || a.starts_at || 0).getTime();
const bS = new Date(b.sort_start_utc || b.start_utc || b.starts_at || 0).getTime();
return aS - bS;
});
exceptionRecords = exceptionRecords.slice(0, 4);
}
const ordered = [];
const pushUnique = (r) => { if (r && !ordered.some((o) => o.id === r.id)) ordered.push(r); };
// Start with the regular weekly schedule, then layer dated exceptions, then authoritative records.
const weekly = all.find((r) => r.id === 'schedule.weekly');
if (weekly) pushUnique(weekly);
for (const r of exceptionRecords) pushUnique(r);
for (const s of candidates) pushUnique(s.record);
if (ordered.length === 0) return null;
const authoritativeAgrees = candidates.some((item) => item.record.authoritative === true);
return { records: ordered.slice(0, 8), dateSpecific, hasException: exceptionRecords.length > 0, authoritativeAgrees };
}
function handleDirections(all, scored, question, intents) {
const isLocationQuery = intents.includes('directions') || intents.includes('location');
if (!isLocationQuery) return null;
// Strongly prefer canonical Urbancrest location/directions records.
const preferred = all.filter((r) => DIRECTIONS_PREFERRED_IDS.has(r.id));
if (preferred.length > 0) return { records: preferred };
// Fall back to highest-scoring location/directions records.
const relevant = scored.filter((s) => {
const r = s.record;
const recIntents = (r.intents || []).map(normalize);
return recIntents.includes('directions') || recIntents.includes('location');
});
if (relevant.length > 0) {
return { records: relevant.slice(0, 4).map((s) => s.record) };
}
return null;
}

const SERMON_MONTHS = {
jan: 1, january: 1, feb: 2, february: 2, mar: 3, march: 3, apr: 4, april: 4,
may: 5, jun: 6, june: 6, jul: 7, july: 7, aug: 8, august: 8, sep: 9, sept: 9,
september: 9, oct: 10, october: 10, nov: 11, november: 11, dec: 12, december: 12,
};
function sermonDateFromQuestion(question, nowMs) {
const nq = normalize(question);
const today = nyDateKey(nowMs);
const yearNow = Number(today.slice(0, 4));
if (/\b(last sunday|this past sunday|previous sunday)\b/.test(nq)) {
const dow = weekdayIndexForDateKey(today);
const back = dow === 0 ? 7 : dow;
return addDaysToDateKey(today, -back);
}
const named = nq.match(/\b(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sept|sep|october|oct|november|nov|december|dec)\s+(\d{1,2})(?:\s*,?\s*(20\d{2}))?\b/);
if (named) {
const month = SERMON_MONTHS[named[1]];
const day = Number(named[2]);
const year = Number(named[3] || yearNow);
if (month && day >= 1 && day <= 31) return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}
const numeric = nq.match(/\b(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?\b/);
if (numeric) {
let year = numeric[3] ? Number(numeric[3]) : yearNow;
if (year < 100) year += 2000;
return `${year}-${String(Number(numeric[1])).padStart(2, '0')}-${String(Number(numeric[2])).padStart(2, '0')}`;
}
return null;
}


function recordCategorySet(record) {
return new Set((record?.category || []).map((value) => normalize(value)));
}
function isSermonSeriesRecord(record) {
if (!record) return false;
if (record.record_type === 'sermon_series') return true;
const categories = recordCategorySet(record);
if (categories.has('sermon_series')) return true;
return /^knowledge\/sermons\/series\//i.test(String(record.path || ''));
}
function isSermonRecord(record) {
if (!record || isSermonSeriesRecord(record)) return false;
if (record.record_type === 'sermon') return true;
const categories = recordCategorySet(record);
if (categories.has('sermon')) return true;
return /^knowledge\/sermons\/(?:19|20)\d{2}\//i.test(String(record.path || ''));
}
function inferredSermonDate(record) {
const direct = String(record?.sermon_date || record?.date || '').trim();
if (/^\d{4}-\d{2}-\d{2}$/.test(direct)) return direct;
const pathMatch = String(record?.path || '').match(/(?:^|\/)(\d{4}-\d{2}-\d{2})(?:-|\.md|\/)/);
if (pathMatch) return pathMatch[1];
const content = String(record?.content || '');
const bodyMatch = content.match(/^(?:\*\*)?Date:(?:\*\*)?\s*(\d{4}-\d{2}-\d{2})\s*$/im);
return bodyMatch?.[1] || '';
}
function inferredSermonSpeaker(record) {
const direct = String(record?.speaker || '').trim();
if (direct) return direct;
const content = String(record?.content || '');
const match = content.match(/^(?:\*\*)?Speaker:(?:\*\*)?\s*([^\n]+)$/im);
return String(match?.[1] || '').replace(/\s{2,}$/g, '').trim();
}
function inferredSermonSeriesTitle(record) {
const direct = String(record?.series_title || '').trim();
if (direct) return direct;
const content = String(record?.content || '');
const match = content.match(/^(?:\*\*)?Series:(?:\*\*)?\s*([^\n]+)$/im);
return String(match?.[1] || '').replace(/\s{2,}$/g, '').trim();
}
function inferredSermonPrimaryScripture(record) {
const direct = String(record?.primary_scripture || '').trim();
if (direct) return direct;
const content = String(record?.content || '');
const match = content.match(/^(?:\*\*)?Primary Scripture:(?:\*\*)?\s*([^\n]+)$/im);
return String(match?.[1] || '').replace(/\s{2,}$/g, '').trim();
}
function inferredSermonNotesUrl(record) {
const direct = String(record?.notes_url || '').trim();
if (direct) return direct;
const resources = Array.isArray(record?.resources) ? record.resources : [];
const resourceUrl = resources.find((value) => /^https:\/\/notes\.subsplash\.com\//i.test(String(value || '')));
if (resourceUrl) return String(resourceUrl);
const content = String(record?.content || '');
const match = content.match(/https:\/\/notes\.subsplash\.com\/[^\s)]+/i);
return match?.[0] || '';
}
function normalizeRuntimeSermonRecord(record, series = false) {
if (!record) return record;
if (series) {
return {
...record,
record_type: 'sermon_series',
series_id: record.series_id || String(record.id || '').replace(/^sermons\.series\./, ''),
};
}
return {
...record,
record_type: 'sermon',
sermon_date: inferredSermonDate(record),
speaker: inferredSermonSpeaker(record),
series_title: inferredSermonSeriesTitle(record),
primary_scripture: inferredSermonPrimaryScripture(record),
notes_url: inferredSermonNotesUrl(record),
};
}

function sermonSpeakerMatches(record, question) {
const nq = normalize(question);
const speaker = normalize(inferredSermonSpeaker(record) || '');
if (!speaker) return false;
const pieces = speaker.split(/\s+/).filter((x) => x.length >= 3);
if (pieces.some((piece) => nq.includes(piece))) return true;
if (speaker.includes('david bickers') && /\b(dave|pastor dave)\b/.test(nq)) return true;
if (speaker.includes('geoff prows') && /\b(pastor geoff)\b/.test(nq)) return true;
return false;
}

function applySermonIntentFromKnownSpeakers(all, question, intents) {
const nq = normalize(question);
const namesKnownSermonSpeaker = (all || []).some(
(record) => isSermonRecord(record) && sermonSpeakerMatches(record, question),
);
if (!namesKnownSermonSpeaker) return;
const hasSpeakerSermonLanguage = /\b(sermon|sermons|message|messages|preach|preached|preaching|said|teach|teaches|taught|teaching)\b/.test(nq);
if (!hasSpeakerSermonLanguage) return;
if (!intents.includes('sermon')) intents.push('sermon');
const generalIndex = intents.indexOf('general');
if (generalIndex >= 0) intents.splice(generalIndex, 1);
}

function sermonQueryTokens(question) {
const extraStops = new Set([...STOPWORDS, 'sermon', 'sermons', 'message', 'messages', 'sunday', 'preach', 'preached', 'pastor', 'notes', 'fill', 'series']);
return tokenize(question).filter((t) => t.length >= 4 && !extraStops.has(t));
}
function handleSermonRetrieval(all, scored, question, intents, nowMs) {
const wantsSeries = intents.includes('sermon_series');
const wantsSermon = intents.includes('sermon');
if (!wantsSeries && !wantsSermon) return null;

const seriesRecords = all
.filter((r) => isSermonSeriesRecord(r))
.map((r) => normalizeRuntimeSermonRecord(r, true));
const sermonRecords = all
.filter((r) => isSermonRecord(r))
.map((r) => normalizeRuntimeSermonRecord(r, false));

if (wantsSeries) {
const nq = normalize(question);
let candidates = [...seriesRecords];
const direct = candidates.filter((r) => {
const title = normalize(r.title || '');
const sid = normalize(r.series_id || '').replace(/_/g, ' ');
return (title && nq.includes(title)) || (sid && nq.includes(sid)) || (title.includes('summer on the mount') && nq.includes('summer on the mount'));
});
if (direct.length > 0) candidates = direct;
if (/\b(current|right now|currently|this summer)\b/.test(nq)) {
const active = candidates.filter((r) => normalize(r.series_status || '') === 'active');
if (active.length > 0) candidates = active;
}
candidates.sort((a, b) => {
const activeA = normalize(a.series_status || '') === 'active' ? 1 : 0;
const activeB = normalize(b.series_status || '') === 'active' ? 1 : 0;
if (activeA !== activeB) return activeB - activeA;
return String(b.start_date || '').localeCompare(String(a.start_date || ''));
});
return { records: candidates.slice(0, 3), isSeries: true };
}

const dateKey = sermonDateFromQuestion(question, nowMs);
if (dateKey) {
const exact = sermonRecords.filter((r) => String(r.sermon_date || '') === dateKey);
return { records: exact.slice(0, 3), isSeries: false };
}

const nq = normalize(question);
if (/\b(latest|last|most recent|recent)\b/.test(nq)) {
const today = nyDateKey(nowMs);
let past = sermonRecords.filter((r) => r.sermon_date && String(r.sermon_date) <= today);
const namesSpeaker = sermonRecords.some((record) => sermonSpeakerMatches(record, question));
if (namesSpeaker) past = past.filter((record) => sermonSpeakerMatches(record, question));
past.sort((a, b) => String(b.sermon_date).localeCompare(String(a.sermon_date)));
return { records: past.slice(0, 1), isSeries: false };
}

const scoreById = new Map(scored.map((item) => [item.record.id, item.score]));
const queryTokens = sermonQueryTokens(question);
const ranked = sermonRecords.map((record) => {
let score = scoreById.get(record.id) || 0;
if (sermonSpeakerMatches(record, question)) score += 180;
const haystack = new Set(tokenize(`${record.title || ''} ${record.summary || ''} ${(record.tags || []).join(' ')} ${(record.search_terms || []).join(' ')} ${record.content || ''} ${record.primary_scripture || ''}`));
for (const token of queryTokens) {
if (haystack.has(token)) score += 35;
}
if (record.series_title && nq.includes(normalize(record.series_title))) score += 100;
return { record, score };
}).filter((item) => item.score > 0)
.sort((a, b) => b.score - a.score || String(b.record.sermon_date || '').localeCompare(String(a.record.sermon_date || '')));

if (ranked.length === 0) return { records: [], isSeries: false };
const plural = /\b(sermons|messages|which|list|all)\b/.test(nq);
return { records: ranked.slice(0, plural ? 8 : 3).map((item) => item.record), isSeries: false };
}


function sermonSeriesArtworkUrl(record) {
const candidates = [
record?.series_artwork_url,
record?.artwork_url,
record?.image_url,
...(Array.isArray(record?.resources) ? record.resources : []),
].filter(Boolean);
for (const candidate of candidates) {
try {
const url = new URL(String(candidate));
if (url.protocol !== 'https:') continue;
if (url.hostname === 'cdn.subsplash.com') return url.toString();
} catch {
// Ignore action-link keys and other non-URL resources.
}
}
return null;
}

function selectServiceActionLink(index) {
const links = (index?.records || []).filter((r) => r && r.record_type === 'action_link');
const plan = links.find((r) => {
const id = normalize(r.id || '');
const title = normalize(r.title || '');
return id === 'plan_visit' || id.includes('plan_visit') || title.includes('plan a visit') || title.includes('plan your visit');
});
return plan || null;
}
function staffQuerySubject(question) {
let subject = normalize(question)
.replace(/[?!.,]+$/g, '')
.replace(/^(please\s+)?(can\s+you\s+)?(tell\s+me\s+about|what\s+can\s+you\s+tell\s+me\s+about|who\s+is|who's|do\s+you\s+know)\s+/i, '')
.replace(/^(your|our)\s+/i, '')
.trim();
return subject;
}
function staffRouteNameAliases(record) {
const title = normalize(record?.title || '');
const display = normalize(record?.display_name || '');
const key = normalize(record?.staff_key || record?.staffKey || '').replace(/_/g, ' ');
const aliases = new Set([title, display, key].filter(Boolean));
const titleParts = title.split(' ').filter(Boolean);
const last = titleParts.length > 1 ? titleParts[titleParts.length - 1] : '';
for (const term of (record?.search_terms || [])) {
const t = normalize(term);
if (!t) continue;
const parts = t.split(' ').filter(Boolean);
// Preserve explicit full-name aliases and nickname + surname forms such as "Matt Kirby".
if (last && parts.length === 1 && /^[a-z][a-z'-]+$/.test(t)) aliases.add(`${t} ${last}`);
if (last && parts.includes(last)) aliases.add(t);
}
return [...aliases].filter((a) => a && a.length >= 3);
}
function isStaffContactDetailQuestion(question) {
const nq = normalize(question);
return /\b(email|e-mail|phone|telephone|extension|contact\s+info|contact\s+information|get\s+in\s+touch|reach)\b/.test(nq)
&& (
  /\b[a-z][a-z'-]*(?:['’]s|s)\s+(email|e-mail|phone|telephone|number|extension)\b/.test(nq) ||
  /\b(email|e-mail|phone|telephone|number|extension)\s+(for|of)\s+[a-z][a-z'-]*\b/.test(nq) ||
  /\b(how\s+do\s+i|can\s+i)\s+(email|call|contact|reach)\s+[a-z][a-z'-]*\b/.test(nq)
);
}
function suppressStaffAssociationForBeliefQuestion(question) {
const nq = normalize(question);
return /\b(lgbtq?|gay|lesbian|bisexual|queer|homosexual(?:ity)?|transgender|nonbinary|same[- ]sex|gender identity|sexual orientation|biblical sexuality)\b/.test(nq);
}
function isStaffLikeQuestion(question, intents) {
const nq = normalize(question);
if ((intents || []).includes('staff')) return true;
if (isStaffContactDetailQuestion(question)) return true;
// "Tell me about" is not inherently a staff query. It may be asking about a ministry,
// program, event, or belief. Explicit staff names are resolved separately by findStaffRoute().
return /\b(who|which)\b.*\b(staff|person|guy|director|pastor|minister|leader|lead|contact|tech|technology|production|finance|facilities|worship|youth|kids|nursery|preschool)\b/.test(nq)
|| /\bwho\b.*\b(takes?\s+care\s+of|manages?|runs?)\b/.test(nq)
|| (/\bwho\b/.test(nq) && /\bIT\b/.test(String(question || '')))
|| /\b(who's|whos)\b/.test(nq)
|| /\b(point\s+person|tech\s+guy|tech\s+person)\b/.test(nq);
}
function expandedStaffQueryTokens(question) {
const tokens = new Set(tokenize(question));
if (tokens.has('tech')) {
tokens.add('technical');
tokens.add('technology');
}
if (tokens.has('av')) {
tokens.add('audio');
tokens.add('video');
}
if (tokens.has('media')) {
tokens.add('production');
tokens.add('video');
}
return tokens;
}
function staffRouteTopicScore(record, question) {
if (!record || (record.record_type !== 'staff' && record.record_type !== 'staff_route')) return 0;
const nq = normalize(question);
const expanded = expandedStaffQueryTokens(question);
const terms = [
...(record.search_terms || []),
...(record.tags || []),
record.role || '',
record.title || '',
record.content || '',
].map(normalize).filter(Boolean);
let score = 0;
for (const term of terms) {
if (term.length >= 4 && nq.includes(term)) score = Math.max(score, 180 + Math.min(term.length, 40));
const termTokens = new Set(tokenize(term));
for (const token of expanded) {
if (token.length >= 4 && termTokens.has(token)) score = Math.max(score, 150 + Math.min(token.length, 30));
}
}
return score;
}
function staffRouteUniqueFirstNameAliases(record) {
const title = normalize(record?.title || '');
const parts = title.split(' ').filter(Boolean);
const first = parts[0] || '';
const display = normalize(record?.display_name || '').replace(/^pastor\s+/, '');
const role = normalize(record?.role || '');
const excluded = new Set([
  ...((record?.ministries || []).map(normalize)),
  ...((record?.routing_topics || []).map(normalize)),
  role, 'staff', 'pastor', 'director', 'minister', 'facilities', 'worship', 'finance', 'production', 'technology',
]);
const candidates = new Set([first, display].filter(Boolean));
for (const raw of [...(record?.routing_aliases || []), ...(record?.search_terms || [])]) {
  const alias = normalize(raw);
  if (!/^[a-z][a-z'-]+$/.test(alias)) continue;
  if (excluded.has(alias)) continue;
  candidates.add(alias);
}
return [...candidates].filter((alias) => alias.length >= 2);
}
function singleNameAliasMatches(question, alias, allowBarePossessiveS = false) {
const escaped = alias.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const suffix = allowBarePossessiveS ? "(?:['’]s|s)?" : "(?:['’]s)?";
return new RegExp(`(^|[^a-z0-9])${escaped}${suffix}([^a-z0-9]|$)`, 'i').test(String(question || ''));
}
function editDistanceAtMostOne(a, b) {
  const left = normalize(a);
  const right = normalize(b);
  if (left === right) return true;
  if (Math.abs(left.length - right.length) > 1) return false;
  let i = 0;
  let j = 0;
  let edits = 0;
  while (i < left.length && j < right.length) {
    if (left[i] === right[j]) { i += 1; j += 1; continue; }
    edits += 1;
    if (edits > 1) return false;
    if (left.length > right.length) i += 1;
    else if (right.length > left.length) j += 1;
    else { i += 1; j += 1; }
  }
  if (i < left.length || j < right.length) edits += 1;
  return edits <= 1;
}
function fuzzyFullStaffNameMatches(subject, alias) {
  const subjectParts = normalize(subject).split(/\s+/).filter(Boolean);
  const aliasParts = normalize(alias).split(/\s+/).filter(Boolean);
  if (subjectParts.length !== 2 || aliasParts.length !== 2) return false;
  // Keep this intentionally narrow: surname must be exact and the first name may
  // have only one edit. This catches "tany byrd" -> "tanya byrd" without turning
  // staff lookup into general fuzzy matching.
  return subjectParts[1] === aliasParts[1] && editDistanceAtMostOne(subjectParts[0], aliasParts[0]);
}

function hasSpecificStaffOwnershipTopic(question) {
const q = String(question || '');
const nq = normalize(q);
return /\b(tech|technical|technology|production|audio|video|livestream|streaming|website|web|finance|finances|financial|stewardship|facilities|facility|building|maintenance|guest services|member services|communications?)\b/.test(nq)
|| /\bIT\b/.test(q)
|| /\binformation technology\b/.test(nq);
}
function findStaffRoute(scored, question, intents, allowGenericFallback = true) {
// Doctrine questions are knowledge questions. Do not let a staff alias/topic mutate
// doctrine retrieval unless the question itself explicitly asks about a staff person.
if ((intents || []).includes('doctrine') && !isStaffLikeQuestion(question, intents)) return null;
const normQ = normalize(question);
const subject = staffQuerySubject(question);
const routes = scored.filter((item) => {
const r = item.record;
return r.record_type === 'staff' || r.record_type === 'staff_route' || !!(r.staff_key || r.staffKey);
});
// Direct staff-key, canonical name, display name, and safe nickname+surname aliases always win.
for (const item of routes) {
const key = normalize(item.record.staff_key || item.record.staffKey || '');
if (key && (normQ.includes(key) || normQ.includes(key.replace(/_/g, ' ')))) return item.record;
}
for (const item of routes) {
const aliases = staffRouteNameAliases(item.record);
if (aliases.some((alias) => subject === alias || normQ === alias || (alias.includes(' ') && normQ.includes(alias)))) return item.record;
}
// Safe typo tolerance for explicit two-part staff names. The surname must match exactly
// and only the first name may differ by one edit.
for (const item of routes) {
  const aliases = staffRouteNameAliases(item.record).filter((alias) => alias.includes(' '));
  if (aliases.some((alias) => fuzzyFullStaffNameMatches(subject, alias))) return item.record;
}
// Resolve a unique first-name/nickname alias for natural staff questions such as
// "Who is Mark?", "What is Mark's email?", or the common no-apostrophe "marks email".
// Single-word aliases are only accepted when they identify exactly one staff route.
const aliasOwners = new Map();
for (const item of routes) {
  for (const alias of staffRouteUniqueFirstNameAliases(item.record)) {
    if (!aliasOwners.has(alias)) aliasOwners.set(alias, []);
    aliasOwners.get(alias).push(item);
  }
}
const allowBarePossessiveS = isStaffContactDetailQuestion(question);
const singleNameStaffContext = isStaffLikeQuestion(question, intents) || isStaffContactDetailQuestion(question);
for (const [alias, owners] of aliasOwners.entries()) {
  if (owners.length !== 1) continue;

  // A unique first name is not enough by itself. Common names can also be ordinary
  // English words (for example, "mark" in "mark where I should park"). Only
  // treat the token as a staff identity when the question is staff-like/contact-related
  // or when the cleaned query subject is exactly that person's name.
  const subjectIsThisName = subject === alias || normQ === alias;
  if (!singleNameStaffContext && !subjectIsThisName) continue;

  if (singleNameAliasMatches(question, alias, allowBarePossessiveS)) return owners[0].record;
}
// Canonical ownership relationships handle ministry/topic ownership. Generic
// staff-route scoring is only a final fallback, and only for staff-like questions.
if (!allowGenericFallback || !isStaffLikeQuestion(question, intents)) return null;
const staffRoutes = routes
.filter((item) => item.record.record_type === 'staff' || item.record.record_type === 'staff_route')
.map((item) => ({ item, score: Math.max(item.score || 0, staffRouteTopicScore(item.record, question)) }))
.sort((a, b) => b.score - a.score);
return staffRoutes[0] && staffRoutes[0].score >= 140 ? staffRoutes[0].item.record : null;
}
function routingTextVariants(value) {
const normalized = normalize(value);
if (!normalized) return [];
const variants = new Set([normalized]);
// Natural ownership questions frequently use possessives: "kid's director",
// "children's director", "women's ministry leader", etc. Relationship aliases
// are usually stored in their non-possessive form, so compare both forms.
variants.add(normalized
.replace(/\b([a-z0-9]+)'s\b/g, '$1')
.replace(/\b([a-z0-9]+)s'\b/g, '$1s')
.replace(/\s+/g, ' ')
.trim());
return [...variants].filter(Boolean);
}
function routingPhraseMatches(question, phrase) {
const raw = String(phrase || '').trim();
if (!raw) return false;
// "IT" is useful as a routing term but dangerous when lowercased because "it"
// is a common pronoun. Require the acronym or a fuller IT phrase.
if (raw.toLowerCase() === 'it') {
return /\bIT\b/.test(question) || /\b(information technology|it support|it department)\b/i.test(question);
}
const questionVariants = routingTextVariants(question);
const phraseVariants = routingTextVariants(raw);
for (const nq of questionVariants) {
for (const p of phraseVariants) {
if (!p) continue;
const escaped = p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
if (new RegExp(`(^|[^a-z0-9])${escaped}([^a-z0-9]|$)`, 'i').test(nq)) return true;
}
}
return false;
}
function ownershipMinistryAliases(record) {
const seeds = [
...(record?.ministries || []),
record?.ministry || '',
];
// The compiled relationship ID is also a reliable canonical fallback even if a
// future index build omits a convenience ministry field.
const idMatch = String(record?.id || '').match(/^relationship\.ministry_staff\.(.+)$/);
if (idMatch?.[1]) seeds.push(idMatch[1].replace(/_/g, ' '));

const aliases = new Set();
for (const seed of seeds.map(normalize).filter(Boolean)) {
aliases.add(seed);
const canon = canonMinistry(seed);
aliases.add(canon);
for (const variant of (MINISTRY_CANON[canon] || [])) aliases.add(variant);
}
return [...aliases].filter(Boolean);
}
function scoreOwnershipRelationship(record, question) {
if (!record || record.record_type !== 'relationship' || record.path !== 'relationships/ministry-staff.yaml') return 0;
const aliases = [
...(record.routing_aliases || []),
...(record.routing_topics || []),
...ownershipMinistryAliases(record),
].filter(Boolean);
let score = 0;
let longest = 0;
for (const term of aliases) {
if (!routingPhraseMatches(question, term)) continue;
const length = normalize(term).length;
longest = Math.max(longest, length);
score = Math.max(score, 180 + Math.min(length, 60));
}
const openRole = record.open_role || '';
if (openRole && routingPhraseMatches(question, openRole)) score = Math.max(score, 260);
if (score > 0 && record.leadership_status === 'vacant') score += 15;
if (score > 0 && record.leadership_status === 'transitional') score += 10;
return score + Math.min(longest, 20);
}
function isPrimaryPastorQuestion(question) {
const nq = normalize(question).replace(/[?!.,]+$/g, '').trim();
return /^(who\s+is|who's|whos)\s+(the\s+|your\s+|our\s+)?((senior|lead|head)\s+)?pastor$/.test(nq)
|| /^(who\s+is|who's|whos)\s+(urbancrest'?s\s+)?((senior|lead|head)\s+)?pastor$/.test(nq);
}
function findOwnershipRelationship(all, question) {
// A singular unqualified "the/your pastor" question means the Senior/lead pastor,
// not whichever staff route happens to score highest on the generic word "pastor".
if (isPrimaryPastorQuestion(question)) {
  const canonicalPastoral = (all || []).find((r) =>
    r && r.record_type === 'relationship' &&
    r.path === 'relationships/ministry-staff.yaml' &&
    (r.id === 'relationship.ministry_staff.pastoral' || (r.ministries || []).map(normalize).includes('pastoral'))
  );
  if (canonicalPastoral) return canonicalPastoral;
}
const candidates = (all || [])
.filter((r) => r && r.record_type === 'relationship' && r.path === 'relationships/ministry-staff.yaml')
.map((record) => ({ record, score: scoreOwnershipRelationship(record, question) }))
.filter((item) => item.score > 0)
.sort((a, b) => b.score - a.score || (b.record.priority || 0) - (a.record.priority || 0));
return candidates[0]?.record || null;
}
function isStaffOwnershipQuestion(question, intents) {
const nq = normalize(question);
if (intents.includes('staff')) return true;
return /\b(who\s+(oversees|leads|handles|takes?\s+care\s+of|manages?|runs?|is\s+responsible)|who\s+(do|should)\s+i\s+(contact|talk\s+to)|point\s+person|who\s+is\s+(?:(?:your|our|the)\s+)?[^?]*(director|pastor|minister|lead|leader|point\s+person)|contact\s+for)\b/.test(nq);
}
function shouldApplyOwnershipRelationship(question, intents, relationship) {
if (!relationship) return false;
// Ownership relationships answer WHO questions. A ministry overview question should be
// answered from ministry knowledge first and may mention a leader only as secondary context.
if (isStaffOwnershipQuestion(question, intents)) return true;
if (isStaffContactDetailQuestion(question)) return true;
return false;
}
function needsStaffProfile(question) {
const nq = normalize(question);
return /\b(about|bio|fun fact|background|tell me about|who is|what does .* do|role)\b/.test(nq);
}
function cleanStaffText(value) {
return String(value || '').trim();
}
function ensureSentence(value) {
const text = cleanStaffText(value);
if (!text) return '';
return /[.!?]$/.test(text) ? text : `${text}.`;
}
function relationshipForStaffKey(all, staffKey) {
const key = normalize(staffKey);
if (!key) return null;
return (all || []).find((record) =>
record && record.record_type === 'relationship' &&
record.path === 'relationships/ministry-staff.yaml' &&
[record.primary_staff_key, record.recommended_contact_staff_key, record.staff_key]
.some((value) => normalize(value) === key)
) || null;
}
function buildDeterministicStaffAnswer(question, staffRoute, relationship, staffProfile) {
const nq = normalize(question);
const name = cleanStaffText(staffProfile?.name || staffRoute?.title || staffRoute?.display_name);
const role = cleanStaffText(staffProfile?.role || staffRoute?.role);
if (!name) return '';

const wantsFunFact = /\b(fun\s*facts?|funfact|something fun|interesting fact)\b/.test(nq);
const wantsBio = /\b(tell me about|bio|biography|background|what does .* do|what is .* role|role at)\b/.test(nq);
const wantsEmail = /\b(email|e-mail|reach|get in touch)\b/.test(nq);

if (wantsFunFact && staffProfile?.funFact) {
return `**${name}**: ${ensureSentence(staffProfile.funFact)}`;
}

if (wantsEmail && staffProfile?.email) {
const roleSentence = role ? `**${name}** serves as **${role}** at Urbancrest.` : `**${name}** is on staff at Urbancrest.`;
return `${roleSentence}\n\nYou can reach ${name.split(' ')[0]} at **${staffProfile.email}**.`;
}

if (isPrimaryPastorQuestion(question)) {
return role
? `**${name}** serves as **${role}** and is Urbancrest's lead pastor.`
: `**${name}** is Urbancrest's lead pastor.`;
}

if (wantsBio && staffProfile?.bio) {
const roleSentence = role ? `**${name}** serves as **${role}** at Urbancrest.` : `**${name}** is on staff at Urbancrest.`;
return `${roleSentence}\n\n${ensureSentence(staffProfile.bio)}`;
}

const wantsOwnershipAnswer = /\b(who\s+(oversees|leads|handles|takes?\s+care\s+of|manages?|runs?|is\s+responsible)|who\s+(do|should)\s+i\s+(contact|talk\s+to)|point\s+person|contact\s+for|who\s+is\s+(your|our|the)\s+.*(guy|person|director|pastor|minister|lead|leader))\b/.test(nq);
if (wantsOwnershipAnswer) {
  // Routing aliases/topics are retrieval metadata, not display copy. Do not echo an
  // answer_guidance string that simply enumerates aliases such as
  // "finance, finances, church finances, giving, stewardship...".
  //
  // For staffed relationships, answer naturally from the canonical person + role
  // and, when possible, the single phrase the user actually asked about.
  if (relationship?.leadership_status === 'vacant' || relationship?.leadership_status === 'transitional') {
    const openRole = cleanStaffText(relationship?.open_role || '');
    const ministryLabel = cleanStaffText(
      relationship?.relationship_label ||
      relationship?.label ||
      String(relationship?.ministry || '').replace(/_/g, ' ')
    );
    const roleArea = openRole
      ? cleanStaffText(openRole.replace(/\b(pastor|director|strategist|administrator|officer|superintendent|lead|leader)\b/gi, '').replace(/\s+/g, ' ').trim())
      : '';
    const contactArea = roleArea || ministryLabel;

    const searchSentence = openRole
      ? `Urbancrest is currently searching for its next **${openRole}**.`
      : ministryLabel
        ? `Urbancrest is currently searching for the next leader for **${ministryLabel}**.`
        : `Urbancrest is currently searching for the next person to lead this ministry.`;

    const contactSentence = role
      ? `In the meantime, **${name}** serves as **${role}** and is the current point person${contactArea ? ` for ${contactArea} questions` : ''}.`
      : `In the meantime, **${name}** is the current point person${contactArea ? ` for ${contactArea} questions` : ''}.`;

    return `${searchSentence} ${contactSentence}`;
  }

  const topicCandidates = [
    ...(relationship?.routing_aliases || []),
    ...(relationship?.routing_topics || []),
    ...(relationship?.ministries || []).map((value) => String(value || '').replace(/_/g, ' ')),
  ]
    .map((value) => cleanStaffText(value))
    .filter(Boolean)
    .filter((value) => routingPhraseMatches(question, value))
    .sort((a, b) => normalize(b).length - normalize(a).length);

  const matchedTopic = topicCandidates[0] || '';
  const firstName = name.split(/\s+/)[0] || name;
  const roleSentence = role
    ? `**${name}** serves as **${role}** at Urbancrest.`
    : `**${name}** is on staff at Urbancrest.`;

  if (matchedTopic) {
    return `${roleSentence} ${firstName} is the primary contact for ${matchedTopic}.`;
  }

  return roleSentence;
}

return role
? `**${name}** serves as **${role}** at Urbancrest.`
: `**${name}** is on staff at Urbancrest.`;
}
function selectActionLink(index, question, intents) {
// Map links are intentionally directions-only. They are selected as a bundle in
// the explicit directions branch and must never participate in generic action-link
// fallback scoring.
const links = (index?.records || []).filter((record) => {
if (!record || record.record_type !== 'action_link') return false;
const linkIntents = (record.intents || []).map(normalize);
if (record.bundle === 'directions_maps' || linkIntents.includes('directions')) return false;
return true;
});
if (links.length === 0) return null;
const normQ = normalize(question);
const scored = links.map((link) => {
let relevance = 0;
const linkIntents = (link.intents || []).map(normalize);
if (linkIntents.some((intent) => intents.some((detected) => intentBase(detected) === intentBase(intent)))) {
relevance += 60;
}
if ((link.search_terms || []).some((term) => {
const t = normalize(term);
return t && (normQ.includes(t) || (normQ.length >= 6 && t.includes(normQ)));
})) {
relevance += 70;
}
// Ignore structural tags that describe the record itself rather than user intent.
if ((link.tags || []).some((tag) => {
const t = normalize(tag);
return t && t !== 'action' && t !== 'link' && normQ.includes(t);
})) {
relevance += 20;
}
// Priority may break ties among relevant links, but it must never make an
// unrelated link eligible by itself.
if (relevance <= 0) return null;
return { link, score: relevance + (link.priority || 0) / 10, relevance };
}).filter(Boolean);
scored.sort((a, b) => b.score - a.score || (b.link.priority || 0) - (a.link.priority || 0));
return scored[0]?.link || null;
}
function selectActionLinkBundle(index, bundleName) {
return (index?.records || [])
.filter((record) => record && record.record_type === 'action_link' && record.bundle === bundleName && record.include_with_bundle === true)
.sort((a, b) => (b.priority || 0) - (a.priority || 0) || String(a.title || '').localeCompare(String(b.title || '')));
}
function formatRecord(r) {
const lines = [`## ${r.title || r.id}`];
if (r.record_type) lines.push(`type: ${r.record_type}`);
if (r.summary) lines.push(r.summary);
if (r.record_type === 'event' || r.record_type === 'small_group') {
const start = r.sort_start_utc || r.start_utc || r.starts_at;
const end = r.sort_end_utc || r.end_utc || r.ends_at;
if (start) lines.push(`starts: ${start}`);
if (end) lines.push(`ends: ${end}`);
if (r.location) lines.push(`location: ${r.location}`);
if (typeof r.registration_available === 'boolean') lines.push(`public registration action available: ${r.registration_available ? 'yes' : 'no'}`);
if (r.registration_url) lines.push(`register: ${r.registration_url}`);
if (r.info_url) lines.push(`event info: ${r.info_url}`);
if (typeof r.registration_open === 'boolean' && r.registration_available !== false) lines.push(`registration open: ${r.registration_open ? 'yes' : 'no'}`);
if (r.registration_at_maximum_capacity === true) lines.push('registration capacity: full');
if (r.registration_open_at) lines.push(`registration opens: ${r.registration_open_at}`);
if (r.registration_close_at) lines.push(`registration closes: ${r.registration_close_at}`);
if (Array.isArray(r.registration_categories) && r.registration_categories.length) lines.push(`registration categories: ${r.registration_categories.join(', ')}`);
if (Array.isArray(r.registration_options) && r.registration_options.length) lines.push(`registration options: ${JSON.stringify(r.registration_options)}`);
}
if (r.record_type === 'schedule') {
if (r.schedule_scope) lines.push(`scope: ${r.schedule_scope}`);
if (r.meetings) lines.push(`meetings: ${typeof r.meetings === 'string' ? r.meetings : JSON.stringify(r.meetings)}`);
if (r.seasonal_note) lines.push(`seasonal note: ${r.seasonal_note}`);
if (r.authoritative) lines.push(`authoritative: true`);
}
if (r.record_type === 'sermon') {
if (r.sermon_date) lines.push(`sermon date: ${r.sermon_date}`);
if (r.speaker) lines.push(`speaker: ${r.speaker}`);
if (r.series_title) lines.push(`series: ${r.series_title}`);
if (r.primary_scripture) lines.push(`primary scripture: ${r.primary_scripture}`);
if (r.notes_url) lines.push(`fill-in notes: ${r.notes_url}`);
if (r.answer_guidance) lines.push(`internal guidance (do not quote): ${r.answer_guidance}`);
}
if (r.record_type === 'sermon_series') {
if (r.series_status) lines.push(`series status: ${r.series_status}`);
if (r.start_date) lines.push(`series start: ${r.start_date}`);
if (r.primary_scripture) lines.push(`primary scripture: ${r.primary_scripture}`);
if (Array.isArray(r.sermons) && r.sermons.length) {
lines.push('series messages:');
for (const sermon of r.sermons) {
lines.push(`- ${sermon.date || ''}: ${sermon.title || ''} - ${sermon.speaker || ''} - ${sermon.primary_scripture || ''}`);
}
}
}
if (r.content) {
const limit = r.record_type === 'sermon' ? 2200 : (r.record_type === 'sermon_series' ? 1600 : 800);
lines.push(String(r.content).slice(0, limit));
}
return lines.join('\n');
}
function formatStaff(s) {
const lines = [`- ${s.name} (key: ${s.key}) - ${s.role || 'Staff'}`];
if (s.bio) lines.push(`Bio: ${s.bio}`);
if (s.funFact) lines.push(`Fun fact: ${s.funFact}`);
if (s.email) lines.push(`Email: ${s.email}`);
return lines.join('\n');
}
function buildPrompt(index, selectedRecords, actionLinks, staffProfile, question, nowStr, pinnedNote = '') {
const config = index?.config || {};
const maxRecords = config.max_retrieval_records || 8;
const personality = config.personality || '';
const styleGuide = config.style_guide || '';
let prompt = '';
if (personality) prompt += personality + '\n\n';
if (styleGuide) prompt += styleGuide + '\n\n';
prompt += RESPONSE_INSTRUCTIONS + '\n\n';
prompt += MARKDOWN_PRESENTATION_INSTRUCTIONS + '\n\n';
if (pinnedNote) prompt += pinnedNote + '\n\n';
prompt += `# CURRENT DATE AND TIME (America/New_York)\n${nowStr}\n\n`;
const records = selectedRecords.slice(0, maxRecords);
if (records.length) {
prompt += `# SELECTED KNOWLEDGE RECORDS\n${records.map(formatRecord).join('\n\n---\n\n')}\n\n`;
} else {
prompt += `# SELECTED KNOWLEDGE RECORDS\nNo directly matching records were found.\n\n`;
}
if (staffProfile) {
prompt += `# SELECTED STAFF PROFILE\n${formatStaff(staffProfile)}\n\n`;
}
if (actionLinks && actionLinks.length > 0) {
const linkLines = actionLinks.map((l) => `- [${l.title}](${l.url})`).join('\n');
prompt += `# SUGGESTED ACTION LINKS\nInclude these as normal markdown links at the end of your answer when they support the next step. When multiple links are provided, include ALL of them. Put each link on its own separate line with a blank line between each link so they render as separate lines:\n${linkLines}\n\n`;
}
prompt += `# USER QUESTION\n${question}`;
return prompt;
}
function logQuietly(promise) {
if (promise && typeof promise.catch === 'function') promise.catch(() => {});
}
function hasInformationalSensitiveFraming(question) {
const nq = normalize(question);
const sensitiveSubject = /\b(suicide|self[- ]?harm|depression|abuse|domestic violence|addiction|divorce|grief|grieving)\b/.test(nq);
if (!sensitiveSubject) return false;
const informational = /\b(what does|what do|what is|what are|believe|belief|biblical|bible|scripture|sermon|message|teaching|doctrine|view on|position on)\b/.test(nq);
const personalDistress = /\b(i am|i'm|i feel|i've|i have|my spouse|my partner|my family|help me|need help|happening to me|hurting me)\b/.test(nq);
return informational && !personalDistress;
}
function hasSchedulingOrResourceFraming(question) {
const nq = normalize(question);
return /\b(when|what time|schedule|meet|meeting|event|group|register|registration|class|study|sermon|message)\b/.test(nq) &&
!/\b(i am|i'm|i feel|i've|i have|help me|need help|hurting me|in danger)\b/.test(nq);
}
function classifySensitiveQuery(question) {
const nq = normalize(question);
if (!nq) return null;

// Critical safety language is evaluated before informational/pastoral routing.
// First distinguish a directly reported crisis affecting another person from a
// first-person crisis so the response addresses the correct person.
const thirdPartySelfHarm = nq.match(
/\b(?:my|our|a) (friend|spouse|partner|husband|wife|child|son|daughter|brother|sister|mom|mother|dad|father|parent|coworker|co-worker|roommate)\b[^.!?]{0,120}\b(suicidal|suicide|wants? to die|doesn'?t want to live|does not want to live|doesn'?t want to be alive|does not want to be alive|can'?t go on|cant go on|cannot go on|kill (?:himself|herself|themself|themselves)|end (?:his|her|their) life)\b/
);
if (thirdPartySelfHarm) {
return {
level: 'critical',
category: 'self_harm',
subject: 'other',
subjectLabel: thirdPartySelfHarm[1] || 'person',
};
}

const selfHarm = [
/\b(i (do not|don't|dont) want to (live|be alive|wake up|exist))\b/,
/\b(i want to die|i wish i were dead|i wish i was dead)\b/,
/\b(i (do not|don't|dont) want to be here anymore)\b/,
/\b(i want (it|everything|this) to end)\b/,
/\b(i (can't|cant|cannot) (go on|keep going|keep living|do this anymore))\b/,
/\b(i'm|im|i am)[^.!?]{0,60}\b(can't|cant|cannot) (go on|keep going|keep living|do this anymore)\b/,
/\b(everyone would be better off without me|no reason to live|nothing to live for)\b/,
/\b(kill myself|end my life|take my life|hurt myself|harm myself)\b/,
/\b(i('m| am)? (thinking about|thinking of|planning|considering) (suicide|killing myself|ending my life|hurting myself|harming myself))\b/,
/\b(i am suicidal|i'm suicidal|im suicidal|suicidal thoughts?)\b/,
/\b(i (might|may|could|will) (kill|hurt|harm) myself)\b/,
/\b(i (have|made) a (suicide )?plan)\b/,
].some((pattern) => pattern.test(nq));
if (selfHarm) return { level: 'critical', category: 'self_harm', subject: 'self' };

const violenceRisk = [
/\b(i (want|plan|intend|am going|'m going) to (kill|shoot|stab|attack|hurt) (someone|him|her|them|my ))/,
/\b(i might hurt someone|i may hurt someone|i could hurt someone|i am afraid i will hurt someone)\b/,
/\b(i (might|may|could) (kill|shoot|stab|attack) someone)\b/,
].some((pattern) => pattern.test(nq));
if (violenceRisk) return { level: 'critical', category: 'violence_risk', subject: 'self' };

const medicalEmergency = [
/\b(i (overdosed|have overdosed))\b/,
/\b(i (took|swallowed) too (many|much) (pills|medicine|medication|drugs))\b/,
/\b(i took an overdose)\b/,
].some((pattern) => pattern.test(nq));
if (medicalEmergency) return { level: 'critical', category: 'medical_emergency', subject: 'self' };

const immediateDanger = [
/\b(i am|i'm|im|we are|we're) not safe\b/,
/\b(i (do not|don't|dont) feel safe)\b/,
/\b(i feel unsafe|we feel unsafe)\b/,
/\b(i am|i'm|im) in (immediate )?danger\b/,
/\b(someone is (trying to )?(hurt|attack|kill) me)\b/,
/\b(i am|i'm|im) being (attacked|threatened|hurt)\b/,
/\b(i (can't|cant|cannot) get away)\b/,
/\b(my (child|children|kid|kids|family) (is|are) not safe)\b/,
].some((pattern) => pattern.test(nq));

const abuseContext = /\b(spouse|partner|husband|wife|boyfriend|girlfriend|abuse|abusive|domestic violence|hurting|attacking|threatening|hits me|hit me|controlling me)\b/.test(nq);
if (immediateDanger && abuseContext) {
return { level: 'critical', category: 'immediate_abuse_danger', subject: 'self' };
}
if (immediateDanger) {
return { level: 'critical', category: 'immediate_danger', subject: 'self' };
}

if (hasInformationalSensitiveFraming(question) || hasSchedulingOrResourceFraming(question)) return null;
if (/\b(abuse|abusive|domestic violence|sexual assault|molested|hits me|hit me|hurting me|unsafe at home|controlling me)\b/.test(nq)) {
return { level: 'sensitive', category: 'abuse' };
}
if (/\b(grief|grieving|bereavement|miscarriage|stillbirth|lost my (mom|mother|dad|father|child|baby|spouse|husband|wife|friend)|someone (close to me )?died)\b/.test(nq)) {
return { level: 'sensitive', category: 'grief' };
}
if (/\b(i am depressed|i'm depressed|depression|i feel hopeless|feeling hopeless|panic attacks?|severe anxiety|emotionally overwhelmed)\b/.test(nq)) {
return { level: 'sensitive', category: 'depression' };
}
if (/\b(i am addicted|i'm addicted|struggling with addiction|can't stop drinking|cannot stop drinking|need help with (drugs|alcohol|pornography|gambling)|substance abuse)\b/.test(nq)) {
return { level: 'sensitive', category: 'addiction' };
}
if (/\b(my marriage is|marriage .* falling apart|considering divorce|getting divorced|separation|family is in crisis|marriage crisis|need marriage help|need marital help)\b/.test(nq)) {
return { level: 'sensitive', category: 'marriage_family' };
}
if (/\b(i need someone to talk to|i need to talk to someone|i'm in a crisis|i am in a crisis|personal crisis|need pastoral help|need pastoral care)\b/.test(nq)) {
return { level: 'sensitive', category: 'pastoral_crisis' };
}
return null;
}

function parseSafetyRegistryConfig(index) {
const record = (index?.records || []).find((item) =>
item && (item.id === 'file.registry/safety.yaml' || item.path === 'registry/safety.yaml')
);
const content = String(record?.content || '');
if (!content) return {};

const categories = ['grief', 'depression', 'abuse', 'addiction', 'marriage_family', 'pastoral_crisis'];
const sensitive_categories = {};

for (const category of categories) {
const marker = `${category}: knowledge_ids:`;
const startAt = content.indexOf(marker);
if (startAt < 0) continue;

let endAt = content.length;
for (const other of categories) {
if (other === category) continue;
const nextAt = content.indexOf(`${other}: knowledge_ids:`, startAt + marker.length);
if (nextAt >= 0 && nextAt < endAt) endAt = nextAt;
}

const block = content.slice(startAt, endAt);
const lines = block.split('\n');
const firstId = lines[0].slice(marker.length).trim();
const knowledge_ids = [];
if (firstId) knowledge_ids.push(firstId);
let staff_key = null;

for (const rawLine of lines.slice(1)) {
const line = rawLine.trim();
if (!line) continue;
if (line.startsWith('staff_key:')) {
staff_key = line.slice('staff_key:'.length).trim() || null;
break;
}
if (/^[a-z_]+:\s/.test(line)) break;
knowledge_ids.push(line);
}

sensitive_categories[category] = {
knowledge_ids: [...new Set(knowledge_ids.filter(Boolean))],
staff_key,
};
}

return { sensitive_categories };
}

function safetyConfig(index) {
const structured = index?.config?.safety;
if (structured && typeof structured === 'object' && Object.keys(structured).length > 0) {
return structured;
}
// The current search index preserves registry/safety.yaml as a registry record rather
// than under index.config.safety. Read the routing from that authoritative record.
return parseSafetyRegistryConfig(index);
}

// Verified against the official 988 Suicide & Crisis Lifeline and SAMHSA on
// 2026-08-17. Critical responses must not depend on the GitHub knowledge index,
// because safety guidance still needs to work during an index/config outage.
const VERIFIED_US_CRISIS_RESOURCES = Object.freeze({
country: 'US',
suicide_crisis_label: '988 Suicide & Crisis Lifeline',
suicide_crisis_phone: '988',
suicide_crisis_text: '988',
suicide_crisis_chat: 'https://988lifeline.org/chat/',
emergency_number: '911',
verified_on: '2026-08-17',
});

function buildCriticalSafetyResponse(index, safety) {
const category = safety?.category || '';
const crisis = VERIFIED_US_CRISIS_RESOURCES;
const lifeline = `call or text **${crisis.suicide_crisis_phone}** for the **${crisis.suicide_crisis_label}**, or use [988 Lifeline chat](${crisis.suicide_crisis_chat})`;

if (category === 'self_harm') {
if (safety?.subject === 'other') {
const label = String(safety?.subjectLabel || 'person');
const personText = /^(friend|coworker|co-worker|roommate)$/i.test(label) ? `your ${label}` : `your ${label}`;
return [
`I'm sorry ${personText} is going through this. Their safety is the priority right now.`,
`If you think they may act on suicidal thoughts or are in immediate danger, call **${crisis.emergency_number}** now. If it is safe for you to do so, stay with them or make sure another trusted person is with them.`,
`In the United States and its territories, they can ${lifeline}. You can also call or text **${crisis.suicide_crisis_phone}** yourself for guidance on helping someone you care about.`,
`Urbancrest pastors can support you and ${personText} too, but crisis or emergency help should come first.`,
].join('\n\n');
}
return [
`I'm really sorry you're hurting. Your safety is the priority right now.`,
`If you might act on these thoughts or could hurt yourself soon, call **${crisis.emergency_number}** now. If you can, do not stay alone, stay with someone you trust, and move away from anything you could use to hurt yourself.`,
`In the United States and its territories, ${lifeline}.`,
`Urbancrest pastors can support you too, but crisis or emergency help should come first.`,
].join('\n\n');
}

if (category === 'immediate_danger') {
return [
`Your safety comes first right now.`,
`If someone may hurt you or you are in immediate physical danger, call **${crisis.emergency_number}** now or move to a safer place if you can do so safely. If possible, stay with someone you trust.`,
`If this is an emotional or mental health crisis, or you are thinking about suicide or self-harm, in the United States and its territories ${lifeline}.`,
`Urbancrest pastors can support you too, but immediate safety and crisis support should come first.`,
].join('\n\n');
}

if (category === 'violence_risk') {
return [
`If you think you may hurt someone, put immediate safety first. Create distance from the person and from any weapon or other means of harm, and do not act on the urge.`,
`If anyone may be harmed now, call **${crisis.emergency_number}**. If this is a mental health crisis and you can safely do so, in the United States and its territories ${lifeline}.`,
`Urbancrest pastors can provide pastoral support after immediate safety has been addressed.`,
].join('\n\n');
}

if (category === 'immediate_abuse_danger') {
return [
`Your immediate safety matters most. If you can do so safely, move to a safer place and call **${crisis.emergency_number}** if you are in immediate danger.`,
`You do not need to confront the person who is hurting or threatening you. Reach out to someone you trust who can help you get somewhere safe.`,
`Urbancrest pastors can provide pastoral support, but immediate safety and appropriate emergency help should come first.`,
].join('\n\n');
}

if (category === 'medical_emergency') {
return [
`A possible overdose or other immediate medical danger needs emergency medical attention now.`,
`Call **${crisis.emergency_number}** now or have someone nearby call for you. Do not rely on church or online advice to manage a possible overdose.`,
].join('\n\n');
}

return `If there is an immediate risk of serious harm, call **${crisis.emergency_number}** and get to a safer place with another trusted person if you can.`;
}

function selectedSensitiveRecords(index, category) {
const config = safetyConfig(index);
const ids = config?.sensitive_categories?.[category]?.knowledge_ids || [];
const wanted = new Set(ids);
return (index?.records || []).filter((r) => r && wanted.has(r.id));
}
function sensitiveStaffKey(index, category) {
return safetyConfig(index)?.sensitive_categories?.[category]?.staff_key || null;
}
function sensitiveActionLinks(index, selectedRecords) {
const selected = selectedRecords || [];
const wantsConnectCard = selected.some((record) => {
if (!record) return false;
if (record.id === 'ministries.stephen_ministry.request_care') return true;
return (record.resources || []).some((value) =>
String(value || '') === 'action_link.connect_card'
|| /churchcenter\.com\/people\/forms\/1494/i.test(String(value || ''))
);
});
if (!wantsConnectCard) return [];

const approved = getActionLinkByKey(index, 'connect_card');
if (approved?.url) return [approved];

for (const record of selected) {
const url = (record.resources || []).find((value) =>
/^https:\/\/urbancrest\.churchcenter\.com\/people\/forms\/1494\/?$/i.test(String(value || ''))
);
if (url) {
return [{
id: 'action_link.connect_card.sensitive_fallback',
action_key: 'connect_card',
title: 'Connect Card',
url: String(url),
}];
}
}
return [];
}
function ensureStephenMinistryCareStep(answer, index, selectedRecords) {
let output = String(answer || '').trim();
const selected = selectedRecords || [];
const hasStephen = selected.some((record) =>
String(record?.id || '').startsWith('ministries.stephen_ministry.')
);
if (!hasStephen) return output;

if (!/\bStephen Ministry\b/i.test(output)) {
output += `${output ? '\n\n' : ''}**Stephen Ministry** is also available for confidential, Christ-centered, one-to-one care through trained lay caregivers who can listen, encourage, pray, and walk alongside you. Stephen Ministers are not professional counselors or therapists.`;
}

const requestRecord = selected.find((record) => record?.id === 'ministries.stephen_ministry.request_care');
const connect = sensitiveActionLinks(index, selected)[0] || null;
if (requestRecord && connect?.url && !output.includes(connect.url)) {
output += `\n\nIf you'd like to be connected with a Stephen Minister, complete the [${connect.title || 'Connect Card'}](${connect.url}) and select **"I'd like to be contacted by a Stephen Minister."**`;
}
return output;
}
function redactSensitiveLogFields(index, safety, question, answer) {
if (!safety) return { question, answer };
const privacy = safetyConfig(index)?.privacy || {};
if (privacy.redact_sensitive_query_logs === false) return { question, answer };
const fmt = privacy.redacted_question_format || '[sensitive query redacted: {category}]';
return {
question: fmt.replace('{category}', safety.category || 'sensitive'),
answer: privacy.redacted_answer || '[sensitive response redacted]',
};
}
function extractPhoneNumbers(text) {
const value = String(text || '');
const matches = value.match(/(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}|\b(?:911|988)\b/g) || [];
return [...new Set(matches.map((n) => n.replace(/\D/g, '')))];
}
function collectApprovedPhones(index, selectedRecords) {
const allowed = new Set();
const addFrom = (value) => extractPhoneNumbers(value).forEach((n) => allowed.add(n));
for (const record of selectedRecords || []) {
addFrom(record.title); addFrom(record.summary); addFrom(record.content);
}
const resources = safetyConfig(index)?.resources || {};
for (const resource of Object.values(resources)) {
if (resource && typeof resource === 'object') {
addFrom(resource.phone); addFrom(resource.text);
}
}
const church = index?.config?.contact?.church || {};
addFrom(church.office_phone);
return allowed;
}
function stripSentencesWithUnapprovedPhoneNumbers(answer, approvedPhones) {
const text = String(answer || '');
const phonePattern = /(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}|\b(?:911|988)\b/g;
const lines = text.split('\n');
const cleaned = [];
for (const line of lines) {
const nums = extractPhoneNumbers(line);
if (nums.length === 0 || nums.every((n) => approvedPhones.has(n))) {
cleaned.push(line);
continue;
}
// Remove only sentences containing an unapproved number so the rest of the
// answer survives. Critical safety responses are deterministic and therefore
// do not depend on this cleanup path.
const parts = line.split(/(?<=[.!?])\s+/);
const safeParts = parts.filter((part) => {
const partNums = extractPhoneNumbers(part);
return partNums.length === 0 || partNums.every((n) => approvedPhones.has(n));
});
cleaned.push(safeParts.join(' '));
}
return cleaned.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}
function isDoctrineKnowledgeRecord(record) {
const path = normalize(record?.path || '');
const categories = (record?.category || []).map(normalize);
const tags = (record?.tags || []).map(normalize);
const intents = (record?.intents || []).map(normalize);
return path.startsWith('knowledge/beliefs/')
|| categories.includes('beliefs')
|| categories.includes('doctrine')
|| tags.includes('beliefs')
|| tags.includes('doctrine')
|| intents.includes('beliefs')
|| intents.includes('doctrine');
}
function doctrineOverridesOperationalIntent(question, intents) {
const nq = normalize(question);
const intentSet = new Set(intents || []);

// Antichrist questions can naturally contain "today" without being calendar questions.
if (/\b(antichrist|anti[- ]christ|man of lawlessness)\b/.test(nq)) return true;

// Sexuality/gender belief questions can naturally contain words such as
// "attend" or "participate" without asking for an event/activity listing.
if (/\b(lgbtq?|gay|lesbian|bisexual|queer|homosexual(?:ity)?|transgender|nonbinary|same[- ]sex|gender identity|sexual orientation|biblical sexuality)\b/.test(nq)) {
return true;
}

// These are inherently doctrinal subjects.
if (/\b(trinity|triune|transubstantiation)\b/.test(nq)) return true;

// Bible-translation questions are doctrinal/informational unless the question
// explicitly points to a particular sermon/date. Those should use sermon data.
const bibleTranslationTopic =
/\b(nasb|nkjv|bible translation|bible translations|bible version|bible versions|word[- ]for[- ]word|thought[- ]for[- ]thought|formal equivalence|dynamic equivalence|functional equivalence)\b/.test(nq)
|| /\b(?:what|which) (?:bible|translation|version)\b[^.!?]{0,55}\b(use|uses|using|preach|preaches|preaching|prefer|prefers)\b/.test(nq)
|| /\bwhat bible do (?:you|we)\b/.test(nq);

if (bibleTranslationTopic) {
if (intentSet.has('sermon') || intentSet.has('sermon_series')) return false;
return true;
}

return false;
}

function selectDoctrineRecords(scored, question, intents, ministries) {
if (!(intents || []).includes('doctrine')) return null;
// Operational questions that merely contain a doctrinal word (for example,
// "sign up for baptism") should continue through their normal action route.
const operationalIntents = new Set([
'calendar', 'registration', 'service_times', 'directions', 'location', 'giving',
'schedule', 'activity_availability', 'small_group', 'sermon', 'sermon_series',
]);
if (
(intents || []).some((intent) => operationalIntents.has(intent))
&& !doctrineOverridesOperationalIntent(question, intents)
) return null;
const normQ = normalize(question);
const tokens = tokenize(question).filter((t) => !STOPWORDS.has(t));
let candidates = (scored || []).filter((item) => {
const r = item.record;
return isGeneralAnswerRecord(r, intents)
&& isDoctrineKnowledgeRecord(r)
&& item.score > 0
&& hasMeaningfulGeneralMatch(r, normQ, tokens, intents, ministries);
});
if (candidates.length === 0) return [];
// Exact canonical belief titles/search terms always beat looser topical overlap.
const exact = candidates.filter((item) => {
const r = item.record;
const title = normalize(r.title || '');
const terms = (r.search_terms || []).map(normalize).filter(Boolean);
return title === normQ || terms.includes(normQ)
|| (title && normQ.includes(title))
|| terms.some((term) => term && normQ.includes(term));
});
if (exact.length > 0) candidates = exact;
candidates.sort((a, b) => b.score - a.score || (b.record.priority || 0) - (a.record.priority || 0));
return candidates.slice(0, 6).map((item) => item.record);
}
function findRecordById(records, id) {
return (records || []).find((record) => record?.id === id) || null;
}
function findDirectDoctrineRecord(records, question, intents) {
if (!(intents || []).includes('doctrine')) return null;
// Registration, calendar, schedule, and other action-oriented questions that happen
// to contain a doctrinal word should continue through their operational handlers.
const operationalIntents = new Set([
'calendar', 'registration', 'service_times', 'directions', 'location', 'giving',
'schedule', 'activity_availability', 'small_group', 'sermon', 'sermon_series',
]);
if (
(intents || []).some((intent) => operationalIntents.has(intent))
&& !doctrineOverridesOperationalIntent(question, intents)
) return null;
const nq = normalize(question);
const candidates = (records || []).filter((record) =>
record && record.record_type === 'knowledge' && isDoctrineKnowledgeRecord(record)
);
if (candidates.length === 0) return null;

// Canonical subject routing. Broad one-word/topic questions must resolve to the
// main doctrine article, not a narrower FAQ that happens to share the same token.

// 0.10.24 belief records are promoted to deterministic routing here.
const asksTransubstantiation =
/\btransubstantiation\b/.test(nq)
|| /\b(?:bread|wafer)\b[^.!?]{0,45}\b(?:become|becomes|turn into|body of (?:jesus|christ))\b/.test(nq)
|| /\b(?:cup|wine)\b[^.!?]{0,45}\b(?:become|becomes|turn into|blood of (?:jesus|christ))\b/.test(nq)
|| /\b(?:literal|literally|actual)\b[^.!?]{0,35}\b(?:body and blood|body|blood)\b/.test(nq)
|| /\bwhat happens\b[^.!?]{0,35}\b(?:bread|cup|wine|elements)\b/.test(nq)
|| /\b(?:bread|cup|wine|elements)\b[^.!?]{0,35}\b(?:symbolic|symbols?)\b/.test(nq);
if (asksTransubstantiation) {
const transubstantiation = findRecordById(candidates, 'beliefs.transubstantiation');
if (transubstantiation) return transubstantiation;
}

const asksTrinity =
/\b(trinity|triune|three in one|three persons)\b/.test(nq)
|| /\bfather\b[^.!?]{0,45}\bson\b[^.!?]{0,45}\bholy spirit\b/.test(nq);
if (asksTrinity) {
const trinity = findRecordById(candidates, 'beliefs.trinity');
if (trinity) return trinity;
}

const asksAntichrist =
/\b(antichrist|anti[- ]christ|man of lawlessness)\b/.test(nq);
if (asksAntichrist) {
const antichrist = findRecordById(candidates, 'beliefs.antichrist');
if (antichrist) return antichrist;
}

const asksSexualityGenderMarriage =
/\b(lgbtq?|gay|lesbian|bisexual|queer|homosexual(?:ity)?|transgender|nonbinary|same[- ]sex|gender identity|biblical sexuality|sexual orientation)\b/.test(nq)
|| (isBroadBeliefQuestion(question) && /\b(sexuality|gender|marriage)\b/.test(nq));
if (asksSexualityGenderMarriage) {
const sexuality = findRecordById(candidates, 'beliefs.sexuality_gender_marriage');
if (sexuality) return sexuality;
}

const asksBibleTranslations =
/\b(nasb|nkjv|bible translation|bible translations|bible version|bible versions|word[- ]for[- ]word|thought[- ]for[- ]thought|formal equivalence|dynamic equivalence|functional equivalence)\b/.test(nq)
|| /\b(?:what|which) (?:bible|translation|version)\b[^.!?]{0,55}\b(use|uses|using|preach|preaches|preaching|prefer|prefers)\b/.test(nq)
|| /\bwhat bible do (?:you|we)\b/.test(nq);
if (asksBibleTranslations) {
const translations = findRecordById(candidates, 'beliefs.bible_translations');
if (translations) return translations;
}

const asksBaptism = /\bbapti(?:sm|ze|zed|zing|se|sed|sing)\b/.test(nq);
const asksBaptismAgain = asksBaptism && /\b(again|re[- ]?bapti|previous|before|baby|infant|childhood|as a child|as a baby)\b/.test(nq);
const asksCommunion = /\b(communion|lord'?s supper)\b/.test(nq);
// Only route to the combined ordinances article when the user explicitly names
// baptism AND Communion / the Lord's Supper as two subjects. A question such as
// "Do I have to be baptized to take communion?" is primarily a Communion-policy
// question and must route to the dedicated Lord's Supper record.
const explicitlyAsksBothOrdinances =
/\bbaptism\b\s*(?:and|&)\s*(?:the\s+)?(?:communion|lord'?s supper)\b/.test(nq)
|| /\b(?:communion|lord'?s supper)\b\s*(?:and|&)\s*(?:the\s+)?baptism\b/.test(nq);
if (explicitlyAsksBothOrdinances) {
const ordinances = findRecordById(candidates, 'beliefs.ordinances');
if (ordinances) return ordinances;
}
if (asksCommunion) {
const lordsSupper = findRecordById(candidates, 'beliefs.lords_supper');
if (lordsSupper) return lordsSupper;
}
if (asksBaptismAgain) {
const again = findRecordById(candidates, 'beliefs.baptism.again');
if (again) return again;
}
if (asksBaptism) {
const meaning = findRecordById(candidates, 'beliefs.baptism.meaning');
if (meaning) return meaning;
}

const asksSuicide = /\b(suicide|suicidal|self[- ]?harm)\b/.test(nq);
if (asksSuicide) {
const suicide = findRecordById(candidates, 'beliefs.suicide');
if (suicide) return suicide;
}

// Specific salvation questions must resolve before broad salvation routing.
// Otherwise a query such as "Can I lose my salvation?" can be swallowed by the
// generic salvation article merely because it contains the word salvation.
const asksAssurance =
/\b(can i know|how can i know|how do i know|know that i am|know that i'm|am i really|assurance)\b/.test(nq)
&& /\b(saved|salvation|christian)\b/.test(nq);
if (asksAssurance) {
const assurance = findRecordById(candidates, 'beliefs.assurance');
if (assurance) return assurance;
}
const asksEternalSecurity =
/\b(lose|lost|losing)\b[^.!?]{0,30}\b(salvation|saved)\b/.test(nq)
|| /\b(eternal security|once saved always saved)\b/.test(nq);
if (asksEternalSecurity) {
const security = findRecordById(candidates, 'beliefs.eternal-security');
if (security) return security;
}
const asksRepentance = /\b(repentance|repent|repenting)\b/.test(nq);
if (asksRepentance) {
const repentance = findRecordById(candidates, 'beliefs.repentance');
if (repentance) return repentance;
}
const asksGospel = /\b(gospel|good news)\b/.test(nq);
if (asksGospel) {
const gospel = findRecordById(candidates, 'beliefs.gospel');
if (gospel) return gospel;
}
const asksSalvation = /\b(salvation|saved|save me|become a christian|follow jesus|trust jesus)\b/.test(nq);
const asksHowToBeSaved = asksSalvation
&& /\b(how|become|want to|need to|what must i|what do i need|how can i)\b/.test(nq)
&& /\b(saved|save me|become a christian|follow jesus|trust jesus)\b/.test(nq);
if (asksHowToBeSaved) {
const getSaved = findRecordById(candidates, 'beliefs.salvation.get-saved');
if (getSaved) return getSaved;
}
if (asksSalvation) {
const salvation = findRecordById(candidates, 'beliefs.salvation');
if (salvation) return salvation;
}

// Stewardship is the canonical doctrine record for belief questions about giving.
// Operational questions such as "How do I give online?" carry the `giving` intent
// and are excluded from direct doctrine routing above.
const asksStewardship =
/\b(stewardship|steward|tithe|tithing|generosity|generous)\b/.test(nq)
|| (/\bgiving\b/.test(nq) && (intents || []).includes('doctrine'));
if (asksStewardship) {
const stewardship = findRecordById(candidates, 'beliefs.stewardship');
if (stewardship) return stewardship;
}

// Exact canonical question/title or search-term match wins for all other doctrines.
for (const record of candidates) {
const title = normalize(record.title || '');
const terms = (record.search_terms || []).map(normalize).filter(Boolean);
if (title === nq || terms.includes(nq)) return record;
}
// For natural variants, prefer the canonical belief record whose metadata contains
// the strongest subject overlap.
const doctrineRoutingWords = new Set([
'urbancrest', 'church', 'believe', 'believes', 'belief', 'beliefs', 'doctrine',
'teaching', 'teach', 'teaches', 'position', 'view', 'views', 'about',
]);
const qTokens = tokenize(question).filter((token) =>
!STOPWORDS.has(token) && token.length >= 4 && !doctrineRoutingWords.has(token)
);
let best = null;
let bestScore = 0;
for (const record of candidates) {
const haystack = new Set(tokenize([
record.title || '',
...(record.search_terms || []),
...(record.tags || []),
record.summary || '',
].join(' ')));
let score = 0;
for (const token of qTokens) if (haystack.has(token)) score += 1;
if (score > bestScore) { best = record; bestScore = score; }
}
return bestScore > 0 ? best : null;
}
function explicitBeliefTopic(question) {
const nq = normalize(question).replace(/[?!.,]+$/g, '').trim();
const patterns = [
/^(?:what does urbancrest believe about)\s+(.+)$/,
/^(?:what does your church believe about)\s+(.+)$/,
/^(?:what do you believe about)\s+(.+)$/,
/^(?:what is urbancrest'?s (?:belief|position|view) (?:on|about))\s+(.+)$/,
/^(?:what is your church'?s (?:belief|position|view) (?:on|about))\s+(.+)$/,
];
for (const pattern of patterns) {
const match = nq.match(pattern);
if (match?.[1]) return match[1].trim();
}
return '';
}

function cleanDoctrineSection(text) {
return String(text || '')
.replace(/^#+\s*/gm, '')
.replace(/\n{3,}/g, '\n\n')
.trim();
}
function getActionLinkByKey(index, key) {
return (index?.records || []).find((record) =>
record && record.record_type === 'action_link' &&
(record.action_key === key || record.id === `action_link.${key}`)
) || null;
}
function selectDoctrineNextStepLink(index, record, question) {
if (!record) return null;
const id = String(record.id || '');
const nq = normalize(question);
const resources = (record.resources || []).map(normalize);

// Baptism questions should offer the baptism interest/signup form as the clearest
// next step. More nuanced rebaptism questions can still use the Connect Card when
// the user is asking for pastoral discernment rather than simply what baptism means.
if (id === 'beliefs.baptism.again' && /\b(again|previous|before|baby|infant|childhood)\b/.test(nq)) {
return getActionLinkByKey(index, 'connect_card') || getActionLinkByKey(index, 'baptism');
}
if (id === 'beliefs.baptism.meaning' && /\b(save|saved|salvation|necessary for salvation|required for salvation|wash away sins|forgiven by baptism)\b/.test(nq)) {
return getActionLinkByKey(index, 'connect_card') || getActionLinkByKey(index, 'baptism');
}
if (id.startsWith('beliefs.baptism') || resources.some((r) => r.includes('baptism'))) {
return getActionLinkByKey(index, 'baptism') || getActionLinkByKey(index, 'connect_card');
}
if ([
'beliefs.salvation',
'beliefs.salvation.get-saved',
'beliefs.assurance',
'beliefs.eternal-security',
'beliefs.repentance',
'beliefs.gospel',
].includes(id)) {
return getActionLinkByKey(index, 'connect_card');
}
if (resources.some((r) => r.includes('connect_card') || r.includes('connect-card'))) {
return getActionLinkByKey(index, 'connect_card');
}
return null;
}

function trimKnownIndexTruncation(text) {
const value = String(text || '').trim();
if (!value.endsWith('...')) return value;
const withoutMarker = value.slice(0, -3).trimEnd();
let lastBoundary = -1;
const boundaryPattern = /[.!?](?=\s|$)/g;
let match;
while ((match = boundaryPattern.exec(withoutMarker)) !== null) lastBoundary = match.index;
if (lastBoundary >= 0) return withoutMarker.slice(0, lastBoundary + 1).trim();
return withoutMarker.trim();
}
function doctrineSectionByHeading(record, heading) {
const content = String(record?.content || '');
const target = normalize(String(heading || '').replace(/[?!:]+$/g, '').trim());
if (!content || !target) return '';

const lines = content.split(/\r?\n/);
let start = -1;
for (let i = 0; i < lines.length; i++) {
const match = lines[i].match(/^##\s+(.+?)\s*$/);
if (!match) continue;
const candidate = normalize(String(match[1] || '').replace(/[?!:]+$/g, '').trim());
if (candidate === target) {
start = i + 1;
break;
}
}
if (start < 0) return '';

let end = lines.length;
for (let i = start; i < lines.length; i++) {
if (/^##\s+/.test(lines[i])) {
end = i;
break;
}
}
const sectionText = lines.slice(start, end).join('\n').trim();
// build_search_index historically capped generic Markdown content and marked the cut
// with "...". If the requested section is the final section in that capped payload,
// never surface the partial trailing sentence to the user.
const safeSectionText = end === lines.length && String(content).trim().endsWith('...')
? trimKnownIndexTruncation(sectionText)
: sectionText;
return cleanDoctrineSection(safeSectionText);
}
function lordSupperAnswerType(question) {
const nq = normalize(question);

// Distinguish "close communion" from "closed communion." Urbancrest practices
// close communion: baptized followers of Jesus may participate; membership is
// not required.
if (/\bclosed communion\b/.test(nq) || /\bopen communion\b/.test(nq)) {
return 'practice_comparison';
}
if (/\bclose communion\b/.test(nq)) {
return 'close_communion';
}

// A negative/unbaptized formulation should answer the practical question first.
if (/\b(not|haven'?t|have not|never)\b[^.!?]{0,40}\bbapti(?:zed|sed|sm)\b/.test(nq)
|| /\bwithout\b[^.!?]{0,25}\bbapti(?:sm|zed|sed)\b/.test(nq)) {
return 'unbaptized';
}
if (/\bbapti(?:sm|zed|sed)\b/.test(nq)
&& /\b(have to|need to|required|must|before|can i|may i|eligible|allowed)\b/.test(nq)) {
return 'baptism_required';
}

if (/\b(non[- ]?members?|not a member|membership|church member|urbancrest member|members?|a member)\b/.test(nq)) {
return 'membership';
}
if (/\b(visitors?|guests?|new to (?:urbancrest|the church)|visiting)\b/.test(nq)) {
return 'visitors';
}
if (/\b(who can|who may|who is allowed|who should|eligible|eligibility|can i take|may i take|can someone take)\b/.test(nq)) {
return 'eligibility';
}

// "What is Communion?" is a definition question. A bare "communion" or
// "What does Urbancrest believe..." gets the concise general-policy answer.
if (/^(what is|what'?s|define|explain)\s+(?:the\s+)?(?:communion|lord'?s supper)\??$/.test(nq)
|| /^(?:the\s+)?(?:communion|lord'?s supper)\??$/.test(nq) && /\bwhat is\b/.test(nq)) {
return 'definition';
}
if (/^(communion|lord'?s supper)$/.test(nq)) return 'general';
if (/\bwhat (?:does|do) (?:urbancrest|you|your church) believe\b/.test(nq)
|| /\bwhat is (?:urbancrest'?s|your) (?:belief|position|view|teaching)\b/.test(nq)) {
return 'general';
}
return 'general';
}
function buildLordSupperDoctrineAnswer(record, question) {
if (!record || record.id !== 'beliefs.lords_supper') return '';
const answerType = lordSupperAnswerType(question);
const shortAnswer = doctrineSectionByHeading(record, 'Short Answer') || cleanDoctrineSection(record.summary || '');
const eligibility = doctrineSectionByHeading(record, 'Who May Participate');
const baptism = doctrineSectionByHeading(record, 'Baptism');
const unbaptized = doctrineSectionByHeading(record, 'If You Have Not Been Baptized');
const membership = doctrineSectionByHeading(record, 'Church Membership');
const visitors = doctrineSectionByHeading(record, 'Visitors and Guests');
const closeCommunion = doctrineSectionByHeading(record, 'What Close Communion Means');
const practiceComparison = doctrineSectionByHeading(record, 'Open, Close, and Closed Communion');
const detailed = doctrineSectionByHeading(record, 'Detailed Answer');

switch (answerType) {
case 'definition':
return shortAnswer;
case 'eligibility':
return eligibility || detailed || shortAnswer;
case 'baptism_required':
return baptism || eligibility || detailed || shortAnswer;
case 'unbaptized':
return unbaptized || baptism || eligibility || detailed || shortAnswer;
case 'membership':
return membership || eligibility || detailed || shortAnswer;
case 'visitors':
return visitors || eligibility || membership || detailed || shortAnswer;
case 'close_communion':
return closeCommunion || detailed || eligibility || shortAnswer;
case 'practice_comparison':
return practiceComparison || closeCommunion || detailed || eligibility || shortAnswer;
case 'general':
default: {
const parts = [];
if (shortAnswer) parts.push(shortAnswer);
if (closeCommunion && normalize(closeCommunion) !== normalize(shortAnswer)) parts.push(closeCommunion);
return parts.join('\n\n') || detailed || eligibility || shortAnswer;
}
}
}

function trinityAnswerType(question) {
const nq = normalize(question);
if (/\bthree gods?\b/.test(nq)) return 'three_gods';
if (/\b(same person|same being in three forms|one person|different forms|modes?)\b/.test(nq)) return 'same_person';
if (/\b(three in one|how can god be three|one in being|three persons)\b/.test(nq)) return 'three_in_one';
if (isDefinitionQuestion(question)) return 'definition';
return 'general';
}
function buildTrinityDoctrineAnswer(record, question) {
if (!record) return '';
const type = trinityAnswerType(question);
const shortAnswer = doctrineSectionByHeading(record, 'Short Answer') || cleanDoctrineSection(record.summary || '');
const threeGods = doctrineSectionByHeading(record, 'Is the Trinity Three Gods');
const samePerson = doctrineSectionByHeading(record, 'Are the Father, Son, and Holy Spirit the Same Person');
const threeInOne = doctrineSectionByHeading(record, 'What Does "Three in One" Mean');
const detail = doctrineSectionByHeading(record, 'Detailed Answer');
switch (type) {
case 'three_gods': return threeGods || detail || shortAnswer;
case 'same_person': return samePerson || detail || shortAnswer;
case 'three_in_one': return threeInOne || detail || shortAnswer;
case 'definition': return shortAnswer;
case 'general':
default: return [shortAnswer, detail].filter(Boolean).join('\n\n');
}
}

function transubstantiationAnswerType(question) {
const nq = normalize(question);
if (
/\bwhat is transubstantiation\b/.test(nq)
|| /\bdefine transubstantiation\b/.test(nq)
|| (isDefinitionQuestion(question) && /\btransubstantiation\b/.test(nq))
) return 'definition';
if (
/\b(?:bread|wafer)\b[^.!?]{0,45}\b(?:body|become|turn into)\b/.test(nq)
|| /\b(?:cup|wine)\b[^.!?]{0,45}\b(?:blood|become|turn into)\b/.test(nq)
|| /\b(?:literal|literally|actual)\b[^.!?]{0,35}\b(?:body|blood)\b/.test(nq)
) return 'literal_elements';
if (/\bwhat happens\b/.test(nq) || /\b(?:symbolic|symbols?|elements)\b/.test(nq)) return 'what_happens';
return 'general';
}
function buildTransubstantiationDoctrineAnswer(record, question) {
if (!record) return '';
const type = transubstantiationAnswerType(question);
const shortAnswer = doctrineSectionByHeading(record, 'Short Answer') || cleanDoctrineSection(record.summary || '');
const definition = doctrineSectionByHeading(record, 'What Is Transubstantiation');
const happens = doctrineSectionByHeading(record, 'What Does Urbancrest Believe Happens During Communion');
const literal = doctrineSectionByHeading(record, "Are the Bread and Cup Literally Jesus' Body and Blood");
const detail = doctrineSectionByHeading(record, 'Detailed Answer');
switch (type) {
case 'definition': return definition || shortAnswer;
case 'literal_elements': return literal || shortAnswer || detail;
case 'what_happens': return happens || shortAnswer || detail;
case 'general':
default: return [shortAnswer, detail].filter(Boolean).join('\n\n');
}
}

function antichristAnswerType(question) {
const nq = normalize(question);
if (/\b(alive today|alive now|already alive|living today|living now)\b/.test(nq)) {
return 'alive_today';
}
if (
/\bwho do you think\b[^.!?]{0,35}\bantichrist\b/.test(nq)
|| /\b(?:identify|identity|today's antichrist|current antichrist)\b/.test(nq)
|| /\b(?:is|could|might|will)\s+[^?]{1,60}\s+(?:the\s+)?antichrist\b/.test(nq)
) return 'identity_speculation';
if (/\b(literal|future|final)\b[^.!?]{0,30}\bantichrist\b/.test(nq)
|| /\bwill there be\b[^.!?]{0,30}\bantichrist\b/.test(nq)) return 'future_person';
if (/\b(afraid|fear|scared|worry|worried|respond|focus)\b/.test(nq)) return 'response';
if (/^who is (?:the )?antichrist\??$/.test(nq)) return 'who_is';
if (isDefinitionQuestion(question)) return 'who_is';
return 'general';
}
function buildAntichristDoctrineAnswer(record, question) {
if (!record) return '';
const type = antichristAnswerType(question);
const shortAnswer = doctrineSectionByHeading(record, 'Short Answer') || cleanDoctrineSection(record.summary || '');
const who = doctrineSectionByHeading(record, 'Who Is the Antichrist');
const future = doctrineSectionByHeading(record, 'Does the Bible Teach That There Will Be a Final Antichrist');
const aliveToday = doctrineSectionByHeading(record, 'Is the Antichrist Alive Today');
const identify = doctrineSectionByHeading(record, 'Can We Know Who the Antichrist Is Today');
const response = doctrineSectionByHeading(record, 'How Should Christians Respond to Teaching About the Antichrist');
const detail = doctrineSectionByHeading(record, 'Detailed Answer');
switch (type) {
case 'who_is': return who || shortAnswer || detail;
case 'future_person': return future || who || shortAnswer;
case 'alive_today': return aliveToday || identify || response || shortAnswer;
case 'identity_speculation': return identify || response || shortAnswer;
case 'response': return response || shortAnswer || detail;
case 'general':
default: return [shortAnswer, detail].filter(Boolean).join('\n\n');
}
}

function sexualityGenderMarriageAnswerType(question) {
const nq = normalize(question);
if (/\b(attend|attending|come to|come here|visit|visiting|welcome|allowed to come|can .* come)\b/.test(nq)
&& /\b(lgbtq?|gay|lesbian|bisexual|queer|homosexual|transgender|same[- ]sex)\b/.test(nq)) return 'attendance';
if (/\b(treat|treated|treatment|hate|love|respect|compassion|welcome|welcoming)\b/.test(nq)) return 'treatment';
if (/\btransgender|nonbinary|gender identity|male and female|gender\b/.test(nq)) return 'gender';
if (/\bsame[- ]sex marriage\b/.test(nq) || /\bmarriage\b/.test(nq)) return 'marriage';
if (/\b(gay|lesbian|homosexual(?:ity)?|same[- ]sex relationship|same[- ]sex relationships)\b/.test(nq)) return 'same_sex';
if (/\bsexuality|sexual orientation|sexual intimacy|sexual behavior\b/.test(nq)) return 'sexuality';
return 'general';
}
function buildSexualityGenderMarriageDoctrineAnswer(record, question) {
if (!record) return '';
const type = sexualityGenderMarriageAnswerType(question);
const shortAnswer = doctrineSectionByHeading(record, 'Short Answer') || cleanDoctrineSection(record.summary || '');
const marriage = doctrineSectionByHeading(record, 'What Does Urbancrest Believe About Marriage');
const sexuality = doctrineSectionByHeading(record, 'What Does Urbancrest Believe About Sexuality');
const gender = doctrineSectionByHeading(record, 'What Does Urbancrest Believe About Gender');
const sameSex = doctrineSectionByHeading(record, 'What Does Urbancrest Believe About Same-Sex Relationships');
const treatment = doctrineSectionByHeading(record, 'How Does Urbancrest Treat People Who Identify as LGBTQ');
const attendance = doctrineSectionByHeading(record, 'Can Someone Who Identifies as LGBTQ Attend Urbancrest');
const detail = doctrineSectionByHeading(record, 'Detailed Answer');
const dignityNote = 'Every person should be treated with dignity, compassion, respect, and Christian love.';
switch (type) {
case 'attendance': return attendance || treatment || shortAnswer;
case 'treatment': return treatment || attendance || shortAnswer;
case 'gender': return [gender, dignityNote].filter(Boolean).join('\n\n') || shortAnswer;
case 'marriage': return [marriage, dignityNote].filter(Boolean).join('\n\n') || shortAnswer;
case 'same_sex': return [sameSex, dignityNote].filter(Boolean).join('\n\n') || shortAnswer;
case 'sexuality': return [sexuality, dignityNote].filter(Boolean).join('\n\n') || shortAnswer;
case 'general':
default: return shortAnswer || treatment;
}
}

function bibleTranslationsAnswerType(question) {
const nq = normalize(question);
const hasGeoff = /\b(geoff|pastor geoff)\b/.test(nq);
const hasDave = /\b(dave|pastor dave)\b/.test(nq);
if (hasGeoff && !hasDave) return 'geoff';
if (hasDave && !hasGeoff) return 'dave';
if (/\b(require|required|only|must use|have to use|one translation|one version)\b/.test(nq)) return 'require_one';
if (/\b(word[- ]for[- ]word|formal equivalence|literal translation)\b/.test(nq)) return 'word_for_word';
if (/\b(thought[- ]for[- ]thought|dynamic equivalence|functional equivalence)\b/.test(nq)) return 'thought_for_thought';
if (/\b(other translation|other translations|another translation|different translation|okay to use|ok to use|can i use)\b/.test(nq)) return 'other_versions';
return 'general';
}
function buildBibleTranslationsDoctrineAnswer(record, question) {
if (!record) return '';
const type = bibleTranslationsAnswerType(question);
const shortAnswer = doctrineSectionByHeading(record, 'Short Answer') || cleanDoctrineSection(record.summary || '');
const geoff = doctrineSectionByHeading(record, 'What Translation Does Pastor Geoff Use');
const dave = doctrineSectionByHeading(record, 'What Translation Does Pastor Dave Use');
const requireOne = doctrineSectionByHeading(record, 'Does Urbancrest Require One Bible Translation');
const wordForWord = doctrineSectionByHeading(record, 'What Is a Word-for-Word Translation');
const thoughtForThought = doctrineSectionByHeading(record, 'What Is a Thought-for-Thought Translation');
const whyFormal = doctrineSectionByHeading(record, 'Why Do Our Pastors Often Use Word-for-Word Translations');
const other = doctrineSectionByHeading(record, 'Are Other Bible Translations Okay to Use');
const detail = doctrineSectionByHeading(record, 'Detailed Answer');
switch (type) {
case 'geoff': return geoff || shortAnswer;
case 'dave': return dave || shortAnswer;
case 'require_one': return requireOne || shortAnswer;
case 'word_for_word': return [wordForWord, whyFormal].filter(Boolean).join('\n\n') || shortAnswer;
case 'thought_for_thought': return thoughtForThought || shortAnswer;
case 'other_versions': return other || requireOne || shortAnswer;
case 'general':
default: return [shortAnswer, requireOne].filter(Boolean).join('\n\n');
}
}

function directDoctrineAnswerType(record, question) {
const id = String(record?.id || '');
if (id === 'beliefs.lords_supper') return lordSupperAnswerType(question);
if (id === 'beliefs.baptism.meaning') return baptismAnswerType(question);
if (id === 'beliefs.baptism.again') return 'rebaptism';
if ([
'beliefs.salvation',
'beliefs.salvation.get-saved',
'beliefs.assurance',
'beliefs.eternal-security',
'beliefs.repentance',
'beliefs.gospel',
].includes(id)) return salvationAnswerType(record, question);
if (id === 'beliefs.stewardship') return stewardshipAnswerType(question);
if (id === 'beliefs.trinity') return trinityAnswerType(question);
if (id === 'beliefs.transubstantiation') return transubstantiationAnswerType(question);
if (id === 'beliefs.antichrist') return antichristAnswerType(question);
if (id === 'beliefs.sexuality_gender_marriage') return sexualityGenderMarriageAnswerType(question);
if (id === 'beliefs.bible_translations') return bibleTranslationsAnswerType(question);
return genericDoctrineAnswerType(question);
}


function isBroadBeliefQuestion(question) {
const nq = normalize(question);
return /\bwhat (?:does|do) (?:urbancrest|you|your church) believe\b/.test(nq)
|| /\bwhat is (?:urbancrest'?s|your) (?:belief|position|view|teaching)\b/.test(nq);
}
function isDefinitionQuestion(question) {
const nq = normalize(question).replace(/[?!.,]+$/g, '').trim();
return /^(what is|what are|what does .+ mean|define|explain)\b/.test(nq);
}
function isDoctrineNextStepQuestion(question) {
const nq = normalize(question);
return /\b(i want to|i'd like to|i would like to|next step|what should i do|what do i do next|talk to a pastor|talk with a pastor|speak to a pastor)\b/.test(nq);
}
function baptismAnswerType(question) {
const nq = normalize(question);
if (/\b(save|saved|salvation|necessary for salvation|required for salvation|wash away sins|forgiven by baptism)\b/.test(nq)) {
return 'salvation_relationship';
}
if (/\b(immersion|immerse|immersed|sprinkl|pour|mode of baptism|how do you baptize|how does urbancrest baptize)\b/.test(nq)) {
return 'immersion';
}
if (/\b(who should|who can|who may|should i|get baptized|be baptized|ready for baptism)\b/.test(nq)) {
return 'candidate';
}
if (isDefinitionQuestion(question)) return 'definition';
if (isBroadBeliefQuestion(question)) return 'general';
return 'general';
}

function actionLinkIs(actionLink, key) {
if (!actionLink) return false;
return actionLink.action_key === key || actionLink.id === `action_link.${key}`;
}
function baptismNextStepText(answerType, actionLink) {
const baptismUrl = actionLinkIs(actionLink, 'baptism') ? actionLink?.url : '';
const connectUrl = actionLinkIs(actionLink, 'connect_card') ? actionLink?.url : '';

if (answerType === 'salvation_relationship') {
if (connectUrl) {
return `If you'd like to talk through salvation and baptism with a pastor, complete the [Connect Card](${connectUrl}) and someone from Urbancrest can follow up with you.`;
}
return `If you'd like to talk through salvation and baptism, one of Urbancrest's pastors would be glad to help.`;
}
if (answerType === 'rebaptism') {
if (connectUrl) {
return `If you're unsure whether you should be baptized again, complete the [Connect Card](${connectUrl}) and a pastor can help you think through your situation.`;
}
return `If you're unsure whether you should be baptized again, one of Urbancrest's pastors can help you think through your situation.`;
}
if (baptismUrl) {
if (answerType === 'candidate') {
return `If you're ready to take baptism as your next step, complete the [Baptism Interest Form](${baptismUrl}) and our team will follow up with you.`;
}
return `If baptism is a next step you're considering, complete the [Baptism Interest Form](${baptismUrl}) and our team will follow up with you.`;
}
if (connectUrl) {
return `If baptism is a next step you're considering, complete the [Connect Card](${connectUrl}) and our team can help you get started.`;
}
return `If baptism is a next step you're considering, talk with one of Urbancrest's pastors and they can help you get started.`;
}
function salvationNextStepText(answerType, actionLink) {
const connectUrl = actionLinkIs(actionLink, 'connect_card') ? actionLink?.url : '';

let text = '';
switch (answerType) {
case 'how_to_be_saved':
text = `If you're ready to follow Jesus or want to talk with someone about salvation,`;
break;
case 'assurance':
case 'assurance_how':
text = `If you're wrestling with assurance or would like to talk through your faith,`;
break;
case 'eternal_security':
text = `If you have questions about your salvation or would like to talk through this with a pastor,`;
break;
case 'repentance':
text = `If you'd like to talk with a pastor about repentance, faith, or following Jesus,`;
break;
case 'gospel':
text = `If you have questions about the gospel or want to talk about following Jesus,`;
break;
case 'works':
text = `If you're wondering what it means to trust Christ rather than your own good works,`;
break;
case 'definition':
case 'general':
default:
text = `If you'd like to talk with a pastor about following Jesus or have questions about salvation,`;
break;
}

if (connectUrl) {
return `${text} complete the [Connect Card](${connectUrl}) and someone from Urbancrest can follow up with you.`;
}
return `${text} one of Urbancrest's pastors would be glad to talk with you.`;
}

function buildBaptismDoctrineAnswer(record, question, actionLink = null) {
if (!record) return '';
if (record.id === 'beliefs.baptism.again') {
const shortAnswer = doctrineSectionByHeading(record, 'Short Answer') || cleanDoctrineSection(record.summary || '');
const detail = doctrineSectionByHeading(record, 'Detailed Answer');
const parts = [shortAnswer, detail].filter(Boolean);
parts.push(baptismNextStepText('rebaptism', actionLink));
return parts.filter(Boolean).join('\n\n');
}
const type = baptismAnswerType(question);
const shortAnswer = doctrineSectionByHeading(record, 'Short Answer') || cleanDoctrineSection(record.summary || '');
const detail = doctrineSectionByHeading(record, 'Detailed Answer');
const candidate = doctrineSectionByHeading(record, 'Who Should Be Baptized');
const salvation = doctrineSectionByHeading(record, 'Does Baptism Save');
const immersion = doctrineSectionByHeading(record, 'Why Immersion');
let answer = '';
switch (type) {
case 'salvation_relationship':
answer = salvation || detail || shortAnswer;
break;
case 'immersion':
answer = immersion || detail || shortAnswer;
break;
case 'candidate':
answer = candidate || detail || shortAnswer;
break;
case 'definition':
answer = shortAnswer;
break;
case 'general':
default:
answer = [shortAnswer, detail].filter(Boolean).join('\n\n');
break;
}
const nextStep = baptismNextStepText(type, actionLink);
return [answer, nextStep].filter(Boolean).join('\n\n').trim();
}
function salvationAnswerType(record, question) {
const id = String(record?.id || '');
const nq = normalize(question);
if (id === 'beliefs.salvation.get-saved') return 'how_to_be_saved';
if (id === 'beliefs.assurance') {
if (/\b(how do i know|how can i know|how would i know)\b/.test(nq)) return 'assurance_how';
return 'assurance';
}
if (id === 'beliefs.eternal-security') return 'eternal_security';
if (id === 'beliefs.repentance') return 'repentance';
if (id === 'beliefs.gospel') return 'gospel';
if (/\b(good works|works save|earn salvation|earn heaven|good enough|being good)\b/.test(nq)) return 'works';
if (isDefinitionQuestion(question)) return 'definition';
return 'general';
}
function buildSalvationDoctrineAnswer(record, question, actionLink = null) {
if (!record) return '';
const type = salvationAnswerType(record, question);
const shortAnswer = doctrineSectionByHeading(record, 'Short Answer') || cleanDoctrineSection(record.summary || '');
const detail = doctrineSectionByHeading(record, 'Detailed Answer');
const grace = doctrineSectionByHeading(record, 'Salvation Is By Grace');
const works = doctrineSectionByHeading(record, 'Good Works Do Not Save');
const repentanceFaith = doctrineSectionByHeading(record, 'Repentance and Faith');
const assuranceHow = doctrineSectionByHeading(record, 'How Can I Know');
let answer = '';
switch (type) {
case 'definition':
answer = shortAnswer;
break;
case 'works':
answer = works || grace || detail || shortAnswer;
break;
case 'how_to_be_saved':
answer = [shortAnswer, detail].filter(Boolean).join('\n\n');
break;
case 'assurance_how':
answer = assuranceHow || detail || shortAnswer;
break;
case 'assurance':
case 'eternal_security':
case 'repentance':
case 'gospel':
answer = [shortAnswer, detail].filter(Boolean).join('\n\n');
break;
case 'general':
default:
answer = [shortAnswer, repentanceFaith || detail].filter(Boolean).join('\n\n');
break;
}
const nextStep = salvationNextStepText(type, actionLink);
return [answer, nextStep].filter(Boolean).join('\n\n').trim();
}
function stewardshipAnswerType(question) {
const nq = normalize(question);
if (/\b(only|just)\b[^.!?]{0,20}\b(money|financial|finances)\b/.test(nq)
|| /\bis stewardship (?:only|just) about money\b/.test(nq)) return 'more_than_money';
if (/\b(why|purpose)\b[^.!?]{0,25}\b(give|giving|generosity|generous)\b/.test(nq)) return 'why_give';
if (/\b(how should|should christians|biblical giving|give cheerfully|give generously)\b/.test(nq)) return 'how_to_give';
if (/\b(giving|give|generosity|generous|tithe|tithing)\b/.test(nq) && isBroadBeliefQuestion(question)) return 'giving';
if (isDefinitionQuestion(question)) return 'definition';
return 'general';
}
function buildStewardshipDoctrineAnswer(record, question) {
if (!record) return '';
const type = stewardshipAnswerType(question);
const shortAnswer = doctrineSectionByHeading(record, 'Short Answer') || cleanDoctrineSection(record.summary || '');
const detail = doctrineSectionByHeading(record, 'Detailed Answer');
const includes = doctrineSectionByHeading(record, 'What Stewardship Includes');
const howGive = doctrineSectionByHeading(record, 'How Christians Should Give');
const whyGive = doctrineSectionByHeading(record, 'Why Giving Matters');
switch (type) {
case 'definition':
return shortAnswer;
case 'more_than_money':
return includes || shortAnswer;
case 'how_to_give':
return howGive || detail || shortAnswer;
case 'why_give':
return whyGive || detail || shortAnswer;
case 'giving':
return [shortAnswer, howGive || detail, whyGive].filter(Boolean).join('\n\n');
case 'general':
default:
return [shortAnswer, detail].filter(Boolean).join('\n\n');
}
}
function genericDoctrineAnswerType(question) {
if (isDefinitionQuestion(question)) return 'definition';
if (isBroadBeliefQuestion(question)) return 'general';
return 'focused';
}
function buildNaturalGenericDoctrineAnswer(record, question, actionLink = null) {
if (!record) return '';
const shortAnswer = doctrineSectionByHeading(record, 'Short Answer') || cleanDoctrineSection(record.summary || '');
const detail = doctrineSectionByHeading(record, 'Detailed Answer');
const type = genericDoctrineAnswerType(question);
let answer = type === 'definition'
? shortAnswer
: [shortAnswer, detail].filter(Boolean).join('\n\n');
if (actionLink?.url && isDoctrineNextStepQuestion(question)) {
answer += `\n\nIf you'd like to talk through this with a pastor, complete the [${actionLink.title || 'Connect Card'}](${actionLink.url}).`;
}
return answer.trim();
}
function buildDirectDoctrineAnswer(record, question, actionLink = null) {
if (!record) return '';
const id = String(record.id || '');
if (id === 'beliefs.lords_supper') return buildLordSupperDoctrineAnswer(record, question);
if (id === 'beliefs.baptism.meaning' || id === 'beliefs.baptism.again') {
return buildBaptismDoctrineAnswer(record, question, actionLink);
}
if ([
'beliefs.salvation',
'beliefs.salvation.get-saved',
'beliefs.assurance',
'beliefs.eternal-security',
'beliefs.repentance',
'beliefs.gospel',
].includes(id)) {
return buildSalvationDoctrineAnswer(record, question, actionLink);
}
if (id === 'beliefs.stewardship') return buildStewardshipDoctrineAnswer(record, question);
if (id === 'beliefs.trinity') return buildTrinityDoctrineAnswer(record, question);
if (id === 'beliefs.transubstantiation') return buildTransubstantiationDoctrineAnswer(record, question);
if (id === 'beliefs.antichrist') return buildAntichristDoctrineAnswer(record, question);
if (id === 'beliefs.sexuality_gender_marriage') return buildSexualityGenderMarriageDoctrineAnswer(record, question);
if (id === 'beliefs.bible_translations') return buildBibleTranslationsDoctrineAnswer(record, question);
return buildNaturalGenericDoctrineAnswer(record, question, actionLink);
}

function buildDeterministicDoctrineAnswer(record, actionLink = null) {
if (!record) return '';
const content = String(record.content || '');
const shortMatch = content.match(/##\s+Short Answer\s*\n+([\s\S]*?)(?=\n##\s+|$)/i);
const detailMatch = content.match(/##\s+Detailed Answer\s*\n+([\s\S]*?)(?=\n##\s+|$)/i);
const infoMatch = content.match(/##\s+Urbancrest Information\s*\n+([\s\S]*?)(?=\n##\s+|$)/i);
const nextStepMatch = content.match(/##\s+Next Step\s*\n+([\s\S]*?)(?=\n##\s+|$)/i);
const shortAnswer = cleanDoctrineSection(shortMatch?.[1] || record.summary || '');
const detailAnswer = cleanDoctrineSection(detailMatch?.[1] || '');
const urbancrestInfo = cleanDoctrineSection(infoMatch?.[1] || '');
const nextStepText = cleanDoctrineSection(nextStepMatch?.[1] || '');
const parts = [];
if (shortAnswer) parts.push(shortAnswer);
if (detailAnswer && normalize(shortAnswer) !== normalize(detailAnswer)) parts.push(detailAnswer);
if (urbancrestInfo) parts.push(urbancrestInfo);
if (actionLink?.url) {
const label = actionLink.title || 'Next Step';
if (actionLink.action_key === 'connect_card' || actionLink.id === 'action_link.connect_card') {
const linkedNextStep = nextStepText
? nextStepText.replace(/\bConnect Card\b/i, `[${label}](${actionLink.url})`)
: `Complete the [${label}](${actionLink.url}) if you would like to talk with a pastor or take a next step.`;
parts.push(linkedNextStep);
} else if (actionLink.action_key === 'baptism' || actionLink.id === 'action_link.baptism') {
parts.push(`If you would like to take the next step, [${label}](${actionLink.url}).`);
} else {
parts.push(`[${label}](${actionLink.url})`);
}
}
return parts.filter(Boolean).join('\n\n') || cleanDoctrineSection(content);
}

function isGeneralAnswerRecord(record, intents = []) {
const type = normalize(record?.record_type || '');
if (type === 'sermon' || type === 'sermon_series') return intents.includes('sermon') || intents.includes('sermon_series');
return type === 'knowledge' || type === 'faq';
}
function hasMeaningfulGeneralMatch(record, normQ, tokens, intents, ministries) {
const title = normalize(record.title || '');
const searchTerms = (record.search_terms || []).map(normalize).filter(Boolean);
if (title && title.length >= 3 && (normQ.includes(title) || (normQ.length >= 4 && title.includes(normQ)))) return true;
if (searchTerms.some((term) => term.length >= 3 && (normQ.includes(term) || (normQ.length >= 5 && term.includes(normQ))))) return true;
const recIntents = (record.intents || []).map(normalize);
if (intents.some((i) => i !== 'general') && recIntents.some((i) => intents.some((di) => intentBase(di) === intentBase(i)))) return true;
const recMin = (record.ministries || []).map(canonMinistry);
const recAud = (record.audiences || []).map(canonMinistry);
if (recMin.some((m) => ministries.includes(m)) || recAud.some((a) => ministries.includes(a))) return true;
const meaningfulTokens = tokens.filter((t) => t.length >= 4);
const tags = new Set((record.tags || []).map(normalize));
if (meaningfulTokens.some((t) => tags.has(t))) return true;
// A natural-language question may reduce to one strong subject token after stopwords
// are removed (for example: "Why are donuts $1?" -> "donuts"). The scorer
// already treats an exact/fuzzy metadata-token match as strong relevance (+90), so
// the eligibility gate must honor the same evidence. Restrict this single-token path
// to tokens of 5+ characters and metadata fields (title, aliases, search terms, tags)
// so generic content words and record priority alone still cannot qualify a record.
const highSignalTokens = meaningfulTokens.filter((t) => t.length >= 5);
if (highSignalTokens.length > 0 && activityMatchedTokens(record, highSignalTokens, true).length > 0) return true;
const contentTokens = new Set(tokenize(`${record.title || ''} ${record.summary || ''} ${record.content || ''}`));
const matched = meaningfulTokens.filter((t) => contentTokens.has(t));
if (meaningfulTokens.length >= 2 && matched.length >= 2) return true;
return false;
}
Deno.serve(async (req) => {
const startedAt = Date.now();
try {
const base44 = createClientFromRequest(req);
const body = await req.json().catch(() => ({}));
const question = (body?.question || '').trim();
if (!question) {
return Response.json({ error: 'question is required' }, { status: 400 });
}
// Critical safety detection intentionally runs before any GitHub/index fetch or
// LLM call. A crisis response must still work if the knowledge source is down.
const safety = classifySensitiveQuery(question);
if (safety?.level === 'critical') {
const answer = buildCriticalSafetyResponse(null, safety);
const confidence = 100;
const retrievedRecordIds = [`safety.critical.${safety.category}`];
const responseTimeMs = Date.now() - startedAt;
const logged = redactSensitiveLogFields(null, safety, question, answer);
logQuietly(base44.asServiceRole.entities.SearchQueryLog.create({
question: logged.question,
answer: logged.answer,
confidence,
staffKey: null,
responseTimeMs,
retrievedRecordIds,
}));
return Response.json({
answer,
staffKey: null,
confidence,
deterministic: true,
answerMode: 'critical_safety',
runtimeVersion: '0.10.33',
safetyCategory: safety.category,
safetySubject: safety.subject || null,
retrievedRecordIds,
});
}

let index = null;
try {
index = await getSearchIndex();
} catch {
index = null;
}
const indexUnavailable = !index;
// Sensitive pastoral queries bypass ordinary knowledge/admin retrieval and use only
// the explicitly vetted records configured for the detected category.
if (safety?.level === 'sensitive') {
const selectedRecords = selectedSensitiveRecords(index, safety.category);
const staffKey = sensitiveStaffKey(index, safety.category);
const nowStr = nyNow();
const pinnedNote = `# SENSITIVE PASTORAL CARE GUIDANCE
This is a sensitive personal-care query. Use only the vetted selected care records. Respond gently, directly, and without diagnosis. If a selected Stephen Ministry record is present, explicitly offer Stephen Ministry as a confidential, Christ-centered, one-to-one lay-care option alongside pastoral care. Do not call Stephen Ministers counselors, therapists, or licensed mental-health professionals. If the Stephen Ministry request-care record is selected, tell the user to complete the Connect Card and select "I'd like to be contacted by a Stephen Minister." Do not invent phone numbers, email addresses, URLs, professional credentials, emergency resources, or church contact details. If the selected record says immediate danger changes the response, state that clearly.`;
const sensitiveLinks = sensitiveActionLinks(index, selectedRecords);
const prompt = buildPrompt(index, selectedRecords, sensitiveLinks, null, question, nowStr, pinnedNote);
const result = await base44.asServiceRole.integrations.Core.InvokeLLM({
prompt,
response_json_schema: {
type: 'object',
properties: {
answer: { type: 'string' },
confidence: { type: 'number', minimum: 0, maximum: 100 },
},
required: ['answer', 'confidence'],
},
});
const approvedPhones = collectApprovedPhones(index, selectedRecords);
const cleanedSensitiveAnswer = stripSentencesWithUnapprovedPhoneNumbers(result?.answer || '', approvedPhones) || 'UNSURE';
const answer = ensureStephenMinistryCareStep(cleanedSensitiveAnswer, index, selectedRecords);
const confidence = selectedRecords.length > 0 ? Math.max(95, Number(result?.confidence || 0)) : 35;
const responseTimeMs = Date.now() - startedAt;
const retrievedRecordIds = selectedRecords.map((r) => r.id).filter(Boolean);
const logged = redactSensitiveLogFields(index, safety, question, answer);
logQuietly(base44.asServiceRole.entities.SearchQueryLog.create({
question: logged.question,
answer: logged.answer,
confidence,
staffKey: staffKey || null,
responseTimeMs,
retrievedRecordIds,
}));
if (!selectedRecords.length) {
logQuietly(base44.asServiceRole.entities.UnansweredQuestion.create({
question: logged.question,
answer: logged.answer,
confidence,
status: 'open',
reviewed: false,
resolved: false,
retrievedRecordIds,
}));
}
return Response.json({ answer, staffKey: staffKey || null, confidence });
}
const adminRecords = await getApprovedAdminRecords(base44).catch(() => []);
const githubRecords = index ? (index.records || []).filter((r) => r && r.record_type !== 'action_link') : [];
const all = [...githubRecords, ...adminRecords];
const intents = detectIntents(question);
const ministries = detectMinistries(question);
applySermonIntentFromKnownSpeakers(all, question, intents);
applyBenevolenceIntents(question, intents, ministries);
// If local_missions_info intent is detected, ensure local_missions ministry is also detected
if (intents.includes('local_missions_info') && !ministries.includes('local_missions')) {
ministries.push('local_missions');
}
// If food_assistance or baskets_of_hope intent is detected, ensure local_missions ministry is also detected
if ((intents.includes('food_assistance') || intents.includes('baskets_of_hope')) && !ministries.includes('local_missions')) {
ministries.push('local_missions');
}
// If food_assistance intent is detected, also add baskets_of_hope intent (Baskets of Hope is the primary pathway)
if (intents.includes('food_assistance') && !intents.includes('baskets_of_hope')) {
intents.push('baskets_of_hope');
}
// Canonical doctrine questions are deterministic data-display requests. Resolve and
// return them BEFORE scoring, event routing, ministry ownership, or staff routing.
// This makes it impossible for a staff relationship (for example Missions -> Jennifer)
// to contaminate a question such as "What does Urbancrest believe about salvation?".
const directDoctrineRecord = findDirectDoctrineRecord(githubRecords, question, intents);
if (directDoctrineRecord) {
const doctrineActionLink = selectDoctrineNextStepLink(index, directDoctrineRecord, question);
const answer = buildDirectDoctrineAnswer(
directDoctrineRecord,
question,
doctrineActionLink
);
const confidence = answer ? 100 : 0;
const responseTimeMs = Date.now() - startedAt;
const retrievedRecordIds = [directDoctrineRecord.id].filter(Boolean);
logQuietly(base44.asServiceRole.entities.SearchQueryLog.create({
question,
answer,
confidence,
staffKey: null,
responseTimeMs,
retrievedRecordIds,
}));
return Response.json({
answer: answer || 'UNSURE',
staffKey: null,
confidence,
deterministic: true,
answerMode: 'direct_doctrine',
doctrineAnswerType: directDoctrineAnswerType(directDoctrineRecord, question),
nextStepActionKey: doctrineActionLink?.action_key || null,
runtimeVersion: '0.10.33',
retrievedRecordIds,
});
}
const unmatchedBeliefTopic = explicitBeliefTopic(question);
if (intents.includes('doctrine') && unmatchedBeliefTopic && !directDoctrineRecord) {
const connectLink = getActionLinkByKey(index, 'connect_card');
const answer = connectLink?.url
? `I don't currently have a dedicated Urbancrest belief article about **${unmatchedBeliefTopic}** in the searchable knowledge base. I don't want to substitute an unrelated doctrine article. If you'd like to talk through the question with a pastor, complete the [${connectLink.title || 'Connect Card'}](${connectLink.url}).`
: `I don't currently have a dedicated Urbancrest belief article about **${unmatchedBeliefTopic}** in the searchable knowledge base. I don't want to substitute an unrelated doctrine article.`;
const confidence = 100;
const responseTimeMs = Date.now() - startedAt;
const retrievedRecordIds = [];
logQuietly(base44.asServiceRole.entities.SearchQueryLog.create({
question,
answer,
confidence,
staffKey: null,
responseTimeMs,
retrievedRecordIds,
}));
return Response.json({
answer,
staffKey: null,
confidence,
deterministic: true,
answerMode: 'unmatched_doctrine_topic',
runtimeVersion: '0.10.33',
retrievedRecordIds,
});
}
const tokens = tokenize(question).filter((t) => !STOPWORDS.has(t));
const normQ = normalize(question);
const scheduleCtx = detectScheduleContext(question, intents);
const scored = all.map((r) => ({ record: r, score: scoreRecord(r, normQ, tokens, intents, ministries, scheduleCtx) }));
scored.sort((a, b) => b.score - a.score);
const nowMs = Date.now();
let selectedRecords = [];
let activityAvailabilityActive = false;
let scheduleActive = false;
let forcedStaffKey = null;
let scheduleIsServiceTimes = false;
let applyConfidenceFloor = false;
let calendarQueryActive = false;
let menuQueryActive = false;
let sermonQueryActive = false;
let sermonSeriesQueryActive = false;
let ministryOverviewActive = false;
let ministryOverviewRecord = null;
let ministryOverviewEvents = [];
// 1. Doctrine/belief questions are knowledge questions first. Restrict them to canonical
// doctrine records so event titles/content and ministry contact records cannot hijack them.
const doctrineSelected = selectDoctrineRecords(scored, question, intents, ministries);
if (doctrineSelected !== null) {
selectedRecords = doctrineSelected;
if (doctrineSelected.length > 0) applyConfidenceFloor = true;
} else {
// 2. Broad ministry/audience questions are ministry-information requests, not staff
// ownership questions or generic activity-availability questions. Resolve the canonical
// ministry overview before those routes have a chance to hijack the answer.
const ministryOverviewResult = selectMinistryOverviewRecords(all, question, intents, ministries);
if (ministryOverviewResult) {
ministryOverviewRecord = ministryOverviewResult.records[0] || null;
ministryOverviewEvents = ministryOverviewRecord
  ? selectUpcomingMinistryEvents(all, ministryOverviewRecord, question, nowMs, 3)
  : [];
selectedRecords = [
  ...ministryOverviewResult.records,
  ...ministryOverviewEvents,
].slice(0, 8);
ministryOverviewActive = true;
applyConfidenceFloor = true;
} else {
// 3. Named live-event lookup comes before recurring schedule routing for specific events.
// Generic service-time questions are an explicit exception: a future service-related event
// must never hijack the canonical recurring Sunday schedule. Dated/holiday questions may
// still consult a matching event as a temporary exception.
const genericServiceTimes = isGenericServiceTimesQuestion(question, intents);
const namedEvent = genericServiceTimes ? null : handleNamedEvent(all, question, nowMs);
if (namedEvent) {
selectedRecords = [namedEvent];
calendarQueryActive = true;
menuQueryActive = ['wednesday_dinner_menu', 'wednesday_dinner_menu_range'].includes(namedEvent.runtime_lookup_type);
applyConfidenceFloor = true;
} else {
// 2. Try generic schedule handler (handles all recurring schedule questions,
// including Sunday service times, ministry schedules, and activity schedules)
const scheduleResult = handleSchedule(all, scored, scheduleCtx, question, nowMs);
if (scheduleResult) {
selectedRecords = scheduleResult.records;
forcedStaffKey = scheduleResult.staffKey;
scheduleActive = true;
scheduleIsServiceTimes = scheduleResult.isServiceTimes;
applyConfidenceFloor = true;
// Service-times questions have a definitive factual answer - no staff contact needed.
if (scheduleIsServiceTimes) forcedStaffKey = null;
// For service-time questions, include the concise article and weekly schedule when available.
if (scheduleIsServiceTimes) {
const seenService = new Set(selectedRecords.map((record) => record.id));
for (const preferredId of ['about.services.times', 'schedule.weekly']) {
const preferredRecord = all.find((record) => record.id === preferredId);
if (preferredRecord && !seenService.has(preferredId) && selectedRecords.length < 8) {
selectedRecords.push(preferredRecord);
seenService.add(preferredId);
}
}
const dateSpecific = isDateSpecific(question);
if (dateSpecific) {
const horizon = nowMs + 21 * 24 * 3600 * 1000;
const exceptionRecords = all.filter((r) => {
if ((r.record_type || '') !== 'event') return false;
if (recordExcludedForServiceTimes(r)) return false;
const start = new Date(r.sort_start_utc || r.start_utc || r.starts_at || 0).getTime();
if (!start || start < nowMs - 24 * 3600 * 1000 || start > horizon) return false;
const title = normalize(r.title || '');
const tags = (r.tags || []).map(normalize);
const isServiceLike = /service|worship|sunday|schedule change|no service|combined service|special service|time change/.test(title)
|| tags.some((t) => /service|worship|schedule/.test(t));
return isServiceLike;
}).sort((a, b) => {
const aS = new Date(a.sort_start_utc || a.start_utc || a.starts_at || 0).getTime();
const bS = new Date(b.sort_start_utc || b.start_utc || b.starts_at || 0).getTime();
return aS - bS;
}).slice(0, 4);
const seen = new Set(selectedRecords.map((r) => r.id));
for (const r of exceptionRecords) {
if (!seen.has(r.id)) { selectedRecords.push(r); seen.add(r.id); }
if (selectedRecords.length >= 8) break;
}
}
}
} else {
// 3. Fall back to existing service-times handler
const serviceOverride = handleServiceTimes(all, scored, question, intents, nowMs);
if (serviceOverride) {
selectedRecords = serviceOverride.records;
scheduleIsServiceTimes = true;
if (serviceOverride.authoritativeAgrees) applyConfidenceFloor = true;
} else {
// 4. Activity availability (searches both schedule and event records)
const activitySelected = handleActivityAvailability(scored, question, intents, nowMs);
if (activitySelected) {
selectedRecords = activitySelected;
activityAvailabilityActive = true;
} else {
// 5. Sermons and sermon series. These are opt-in so historical sermon language
// never competes with canonical doctrine or ministry knowledge on general questions.
const sermonSelected = handleSermonRetrieval(all, scored, question, intents, nowMs);
if (sermonSelected !== null) {
selectedRecords = sermonSelected.records;
sermonQueryActive = !sermonSelected.isSeries;
sermonSeriesQueryActive = sermonSelected.isSeries;
if (selectedRecords.length > 0) applyConfidenceFloor = true;
} else {
// 6. Calendar / events
const calendarSelected = handleCalendar(all, question, intents, ministries, nowMs);
if (calendarSelected !== null) {
selectedRecords = calendarSelected;
calendarQueryActive = true;
if (calendarSelected.length > 0) applyConfidenceFloor = true;
} else {
// 7. Directions
const directionsResult = handleDirections(all, scored, question, intents);
if (directionsResult) {
selectedRecords = directionsResult.records;
applyConfidenceFloor = true;
} else {
// 8. General fallback. Priority alone never makes a record eligible.
selectedRecords = scored
.filter((s) => isGeneralAnswerRecord(s.record, intents) && s.score > 0 && hasMeaningfulGeneralMatch(s.record, normQ, tokens, intents, ministries))
.slice(0, 8)
.map((s) => s.record);
}
}
}
}
}
}
}
}
}
// Wednesday Night Dinner menu questions are structured live-data lookups. Format them
// directly so single dates and month/range requests never fall through to unrelated
// ministry knowledge or require InvokeLLM to concatenate menu entries.
if (menuQueryActive && selectedRecords[0]) {
const answer = buildDeterministicWednesdayDinnerMenuAnswer(selectedRecords[0]);
if (answer) {
const confidence = 100;
const responseTimeMs = Date.now() - startedAt;
const retrievedRecordIds = [
...(selectedRecords[0].runtime_source_event_ids || []),
...(selectedRecords[0].id ? [selectedRecords[0].id] : []),
].filter(Boolean);
logQuietly(base44.asServiceRole.entities.SearchQueryLog.create({
question,
answer,
confidence,
staffKey: null,
responseTimeMs,
retrievedRecordIds,
}));
return Response.json({
answer,
staffKey: null,
confidence,
deterministic: true,
answerMode: selectedRecords[0].runtime_lookup_type === 'wednesday_dinner_menu_range'
? 'direct_wednesday_dinner_menu_range'
: 'direct_wednesday_dinner_menu',
runtimeVersion: '0.10.33',
retrievedRecordIds,
});
}
}

// Staff routing
let staffKey = forcedStaffKey || null;
let staffProfile = null;
let matchedStaffRoute = null;
let matchedStaffRelationship = null;
const staffRoutingAllowed =
!ministryOverviewActive
&& !sermonQueryActive
&& !sermonSeriesQueryActive
&& !suppressStaffAssociationForBeliefQuestion(question)
&& (!intents.includes('doctrine') || isStaffLikeQuestion(question, intents));
const ownershipRelationship = staffRoutingAllowed ? findOwnershipRelationship(all, question) : null;
const ownershipQuestion = staffRoutingAllowed && (isStaffOwnershipQuestion(question, intents) || isStaffLikeQuestion(question, intents));
const applyOwnership = shouldApplyOwnershipRelationship(question, intents, ownershipRelationship);
// If the user is explicitly asking who leads/oversees/handles an area, include the
// canonical relationship record in context so vacancy/transitional guidance is visible.
if (ownershipRelationship && ownershipQuestion) {
matchedStaffRelationship = ownershipRelationship;
const existing = new Set(selectedRecords.map((r) => r.id));
if (!existing.has(ownershipRelationship.id)) {
selectedRecords = [ownershipRelationship, ...selectedRecords].slice(0, 8);
}
applyConfidenceFloor = true;
}
// 1. Explicit staff-name mention. This also understands safe name aliases such as "Matt Kirby".
const explicitStaffRoute = staffRoutingAllowed ? findStaffRoute(scored, question, intents, false) : null;
if (explicitStaffRoute) {
matchedStaffRoute = explicitStaffRoute;
if (!staffKey) staffKey = explicitStaffRoute.staff_key || explicitStaffRoute.staffKey || null;
const existing = new Set(selectedRecords.map((r) => r.id));
if (!existing.has(explicitStaffRoute.id)) {
selectedRecords = [explicitStaffRoute, ...selectedRecords].slice(0, 8);
}
applyConfidenceFloor = true;
}
// 2. Canonical ministry/role ownership. This MUST run before generic staff-route
// scoring so phrases such as "lead pastor" resolve to the canonical Senior
// Leadership relationship (Geoff Prows), not whichever pastoral route happens
// to have the highest retrieval score.
if (!staffKey && applyOwnership && ownershipRelationship) {
staffKey = ownershipRelationship.primary_staff_key ||
ownershipRelationship.recommended_contact_staff_key ||
ownershipRelationship.staff_key ||
null;
matchedStaffRelationship = ownershipRelationship;
}
// 3. Staff-topic fallback for natural phrases such as "who is your tech guy?".
// If the user clearly asked an ownership/leadership question but no canonical
// relationship matched, NEVER guess from generic staff titles/topics. It is safer
// to return no staff card than to turn an unrelated Director into the answer.
if (!staffKey && staffRoutingAllowed && (!ownershipQuestion || ownershipRelationship || hasSpecificStaffOwnershipTopic(question))) {
const fallbackStaffRoute = findStaffRoute(scored, question, intents, true);
if (fallbackStaffRoute) {
matchedStaffRoute = fallbackStaffRoute;
staffKey = fallbackStaffRoute.staff_key || fallbackStaffRoute.staffKey || null;
const existing = new Set(selectedRecords.map((r) => r.id));
if (!existing.has(fallbackStaffRoute.id)) {
selectedRecords = [fallbackStaffRoute, ...selectedRecords].slice(0, 8);
}
applyConfidenceFloor = true;
}
}
// 4. Named Base44 Staff fallback for explicit staff questions. This is profile/card data,
// while GitHub remains the canonical routing source when a route is available.
if (!staffKey && isStaffLikeQuestion(question, intents)) {
try {
const staffList = await getStaffCollection(base44);
const subject = staffQuerySubject(question);
const named = staffList.find((s) => {
const full = normalize(s.name);
if (!full) return false;
if (subject === full || normQ.includes(full)) return true;
if (fuzzyFullStaffNameMatches(subject, full)) return true;
const parts = full.split(' ').filter(Boolean);
return parts.length > 1 && subject.endsWith(` ${parts[parts.length - 1]}`) && subject.split(' ').some((p) => p === parts[0]);
});
if (named) staffKey = named.key || null;
} catch {
// ignore
}
}
// 5. Direct-answer metadata fallback. Only the top selected record may nominate a
// contact. Never scan arbitrary secondary records for the first staff key.
if (
!staffKey
&& !ministryOverviewActive
&& !scheduleIsServiceTimes
&& selectedRecords.length > 0
&& !isStaffLikeQuestion(question, intents)
&& !intents.includes('doctrine')
&& !suppressStaffAssociationForBeliefQuestion(question)
) {
const topRecord = selectedRecords[0];
staffKey = topRecord.primary_staff_key ||
topRecord.recommended_contact_staff_key ||
topRecord.staff_key ||
null;
}
// Doctrine answers should not acquire a staff card from incidental routing metadata.
// A staff card is allowed only when the doctrine question itself is explicitly staff-like.
if (
(intents.includes('doctrine') && !isStaffLikeQuestion(question, intents))
|| suppressStaffAssociationForBeliefQuestion(question)
) {
staffKey = null;
matchedStaffRoute = null;
matchedStaffRelationship = null;
}
// If a route identified the person, attach that person's canonical ministry relationship too.
if (staffKey && !matchedStaffRelationship) {
matchedStaffRelationship = relationshipForStaffKey(all, staffKey);
}
// Load the Base44 Staff profile whenever a staff identity was explicitly resolved. This keeps
// the written answer and the frontend staff card on the same person/source.
if (staffKey && (matchedStaffRoute || matchedStaffRelationship || needsStaffProfile(question) || ownershipQuestion || intents.includes('staff'))) {
try {
const staffList = await getStaffCollection(base44);
staffProfile = findStaffByKey(staffList, staffKey);
} catch {
// ignore
}
}
// A named preacher is sermon retrieval context, not a request for a staff biography.
if (sermonQueryActive || sermonSeriesQueryActive) {
staffKey = null;
staffProfile = null;
matchedStaffRoute = null;
matchedStaffRelationship = null;
}
// Staff identity and ownership questions are data-display requests too. Once the staff key is
// resolved, answer from the canonical route/relationship plus the Base44 Staff profile instead
// of asking the LLM to reconcile an empty knowledge-record section with a visible staff card.
if (staffKey && (matchedStaffRoute || (matchedStaffRelationship && isStaffLikeQuestion(question, intents)))) {
const answer = buildDeterministicStaffAnswer(question, matchedStaffRoute, matchedStaffRelationship, staffProfile);
if (answer) {
const confidence = 100;
const responseTimeMs = Date.now() - startedAt;
const retrievedRecordIds = [matchedStaffRoute?.id, matchedStaffRelationship?.id].filter(Boolean);
logQuietly(base44.asServiceRole.entities.SearchQueryLog.create({
question,
answer,
confidence,
staffKey,
responseTimeMs,
retrievedRecordIds,
}));
return Response.json({
answer,
staffKey,
confidence,
deterministic: true,
answerMode: ownershipQuestion ? 'staff_ownership' : 'staff_identity',
runtimeVersion: '0.10.33',
retrievedRecordIds,
});
}
}

// Regular service-time questions are canonical data-display requests, not open-ended writing tasks.
// Format them directly so "What time are Sunday services?" is stable and cannot be replaced
// by an unrelated future service event. Date-specific questions intentionally remain on the
// exception-aware path below.
if (scheduleIsServiceTimes && isGenericServiceTimesQuestion(question, intents) && selectedRecords.length > 0) {
const planLink = selectServiceActionLink(index);
const answer = buildDeterministicRegularServiceTimesAnswer(selectedRecords, planLink);
if (answer) {
const confidence = 100;
const responseTimeMs = Date.now() - startedAt;
const retrievedRecordIds = selectedRecords.map((record) => record.id).filter(Boolean);
logQuietly(base44.asServiceRole.entities.SearchQueryLog.create({
question,
answer,
confidence,
staffKey: null,
responseTimeMs,
retrievedRecordIds,
}));
return Response.json({ answer, staffKey: null, confidence, deterministic: true, answerMode: 'direct_service_times', runtimeVersion: '0.10.33', retrievedRecordIds });
}
}

// Location and directions questions are also simple data-display requests. Keep them
// deterministic so the address and approved map links stay consistent, while using a
// warmer response than a bare address dump.
if ((intents.includes('directions') || intents.includes('location')) && selectedRecords.length > 0) {
let directionLinks = [];
if (index) {
directionLinks = selectActionLinkBundle(index, 'directions_maps');
if (directionLinks.length === 0) {
directionLinks = (index?.records || []).filter((record) =>
record && record.record_type === 'action_link' &&
(record.intents || []).map(normalize).includes('directions')
);
}
}
const answer = buildDeterministicDirectionsAnswer(directionLinks);
const confidence = 100;
const responseTimeMs = Date.now() - startedAt;
const retrievedRecordIds = selectedRecords.map((record) => record.id).filter(Boolean);
logQuietly(base44.asServiceRole.entities.SearchQueryLog.create({
question,
answer,
confidence,
staffKey: null,
responseTimeMs,
retrievedRecordIds,
}));
return Response.json({
answer,
staffKey: null,
confidence,
deterministic: true,
answerMode: 'direct_directions',
runtimeVersion: '0.10.33',
retrievedRecordIds,
});
}

// A live-event query must never interpret an unavailable search index as an empty calendar.
// On a cold serverless invocation, GitHub can occasionally be temporarily unreachable.
if (calendarQueryActive && selectedRecords.length === 0 && indexUnavailable) {
const answer = 'I’m having trouble loading the current event calendar right now. Please try again in a moment.';
const confidence = 0;
const responseTimeMs = Date.now() - startedAt;
logQuietly(base44.asServiceRole.entities.SearchQueryLog.create({
question,
answer,
confidence,
staffKey: null,
responseTimeMs,
retrievedRecordIds: [],
}));
return Response.json({ answer, staffKey: null, confidence, dataStatus: 'temporarily_unavailable' });
}

// Plural event-list questions are data-display requests, not open-ended writing tasks.
// Format them directly so the same query returns the same events, order, times, and wording.
if (calendarQueryActive && selectedRecords.length > 0 && !isSingularRequest(question)) {
const viewAllLink = selectViewAllEventsLink(index);
const answer = buildDeterministicUpcomingEventsAnswer(selectedRecords, viewAllLink);
const confidence = 100;
const responseTimeMs = Date.now() - startedAt;
const retrievedRecordIds = selectedRecords.map((record) => record.id).filter(Boolean);
logQuietly(base44.asServiceRole.entities.SearchQueryLog.create({
question,
answer,
confidence,
staffKey: null,
responseTimeMs,
retrievedRecordIds,
}));
return Response.json({ answer, staffKey: null, confidence, deterministic: true });
}

// Broad ministry/audience overview questions are also deterministic data-display
// requests. Render the canonical ministry article directly, then enrich it from the
// already-loaded live event records. This preserves current information without an
// InvokeLLM call, so the answer stays fast, consistent, and low-cost.
if (ministryOverviewActive && ministryOverviewRecord) {
const viewAllLink = selectViewAllEventsLink(index);
const answer = buildDeterministicMinistryOverviewAnswer(
  ministryOverviewRecord,
  ministryOverviewEvents,
  viewAllLink,
);
const confidence = answer ? 100 : 0;
const responseTimeMs = Date.now() - startedAt;
const retrievedRecordIds = selectedRecords.map((record) => record.id).filter(Boolean);
logQuietly(base44.asServiceRole.entities.SearchQueryLog.create({
  question,
  answer,
  confidence,
  staffKey: null,
  responseTimeMs,
  retrievedRecordIds,
}));
return Response.json({
  answer: answer || 'UNSURE',
  staffKey: null,
  confidence,
  deterministic: true,
  answerMode: 'ministry_overview_enriched',
  runtimeVersion: '0.10.33',
  retrievedRecordIds,
  eventRecordIds: ministryOverviewEvents.map((record) => record.id).filter(Boolean),
  eventTitles: ministryOverviewEvents.map((record) => record.title).filter(Boolean),
});
}

let actionLinks = [];
if (index) {
if (intents.includes('directions') || intents.includes('location')) {
// Location/directions: try the complete map bundle first, then fall back to all direction links.
actionLinks = selectActionLinkBundle(index, 'directions_maps');
if (actionLinks.length === 0) {
actionLinks = (index?.records || []).filter(r =>
r && r.record_type === 'action_link' &&
(r.intents || []).map(normalize).includes('directions')
);
}
} else {
const primary = selectActionLink(index, question, intents);
if (primary) {
if (primary.include_with_bundle && primary.bundle) {
actionLinks = selectActionLinkBundle(index, primary.bundle);
} else {
actionLinks = [primary];
}
}
// Plan Your Visit for service-times (not when directions is primary intent)
if (scheduleIsServiceTimes) {
const planLink = selectServiceActionLink(index);
if (planLink) actionLinks = [planLink];
}
}
}
const nowStr = nyNow();
let pinnedNote = '';
if (scheduleActive && scheduleIsServiceTimes) {
pinnedNote = `# SERVICE TIMES GUIDANCE
Use the authoritative recurring service-time records in the selected context and state their times plainly. Do not substitute routine dated service occurrences for the recurring schedule. If the selected records contain an explicit dated schedule exception for the requested date, explain that exception.`;
} else if (scheduleActive) {
pinnedNote = `# SCHEDULE GUIDANCE\nUse the schedule stated directly in the selected knowledge record. State the schedule plainly and confidently. Do not add uncertainty such as "times may vary" or "check with the office." If the record notes a regular seasonal pause (such as a summer break), include that explanation. Do not defer to the church office when the record contains the answer.`;
} else if (ministryOverviewActive) {
pinnedNote = `# MINISTRY OVERVIEW GUIDANCE
The user is asking what this ministry is or what Urbancrest offers for this audience. Lead with the selected canonical ministry knowledge record and answer the ministry question directly. Do not turn the response into a staff biography or leadership answer. Do not repeat routing aliases or staff search terms. A leader or contact may be mentioned only as secondary context if the selected ministry record explicitly includes that information. If the selected record contains a current leadership transition, keep that secondary to the ministry description unless the user asks who leads it.`;
} else if (activityAvailabilityActive) {
pinnedNote = `# ACTIVITY AVAILABILITY GUIDANCE\nThe selected records for this activity may include recurring schedule records and/or calendar event occurrences. If a recurring schedule record is present, describe the activity as regularly offered. If only event records are present, describe the activity as a scheduled or recurring event (for example, "Open Gym Pickleball meets Thursday evenings"). Do not describe it as a permanent ministry, program, or department unless a selected knowledge record explicitly states that it is one.`;
} else if (sermonSeriesQueryActive) {
pinnedNote = `# SERMON SERIES GUIDANCE
Use the selected sermon-series record and its structured series message list. State the series title, scope, and message history directly. The sermon list is historical and chronological. Do not present sermon summaries as the church's canonical doctrine when a dedicated beliefs article exists.`;
} else if (sermonQueryActive && selectedRecords.length > 0) {
pinnedNote = `# SERMON GUIDANCE
The selected records are historical Urbancrest sermon summaries. Answer what was preached using the sermon date, speaker, Scripture, main idea, and outline in the selected record. If the user asks for fill-in notes, include the exact notes.subsplash.com URL from the selected record. Do not invent a notes URL. Do not treat a sermon summary as the canonical statement of Urbancrest doctrine, policy, schedule, or current ministry information when a dedicated knowledge record exists.`;
} else if (sermonQueryActive && selectedRecords.length === 0) {
pinnedNote = `# SERMON GUIDANCE
No matching sermon record was found for the requested date, speaker, series, or topic. Say that the searchable sermon records do not currently contain a matching message. Do not substitute an unrelated sermon.`;
} else if (menuQueryActive) {
pinnedNote = `# WEDNESDAY NIGHT DINNER MENU GUIDANCE
The selected record is a compact lookup derived from the current live Planning Center Wednesday Night Dinner event. Answer the user's menu question from this record only. Give the menu information contained in the selected live lookup record. For a range lookup, include every listed dinner date in the requested range; for a single-date lookup, give only that date. If a recurring menu note is present, include it after the date-specific menu. If the record says no menu is currently listed for that date, say that plainly and do not guess. Keep the response concise and do not refer the user to the church office when the live record already answers the question.`;
} else if (calendarQueryActive && selectedRecords.length === 0) {
pinnedNote = `# LIVE EVENT GUIDANCE
The current live event index contains no future event matching the user's requested ministry, activity, or date window. State that no matching upcoming event is currently listed. Do not substitute an unrelated event.`;
} else if (calendarQueryActive && selectedRecords.length > 0) {
pinnedNote = `# UPCOMING EVENT GUIDANCE
The selected records include live event records from Urbancrest's calendar and/or Planning Center Registrations with specific dates, times, locations, and public Church Center state. Answer from the event record directly - state the event title, date, time, and location from the structured fields. A registration link is valid ONLY when registration_available is true AND an exact registration_url is present. If registration_available is false, do not provide, construct, or infer a registration link; if the user asks how to register, say that no public registration action is currently available for that event. The info_url is an event-details page, not a registration link. If registration_open is false or registration_closed is true, do not describe registration as open. If registration_at_maximum_capacity is true, state that registration is full. When registration_options are present, use their exact names and price fields for cost questions; if option prices differ, explain the options instead of inventing one event-wide price. Use selection-level capacity or waitlist fields only when they are explicitly present. Do not infer registration availability from API open/closed fields or from an info URL. Do not defer to a static article or the church office when a matching event record is present. If the user asked for the next occurrence, return the earliest matching future event.`;
} else if (intents.includes('directions') || intents.includes('location')) {
pinnedNote = `# LOCATION AND DIRECTIONS GUIDANCE\nState the church address plainly from the selected knowledge record. The canonical Urbancrest address is 2634 Drake Road, Lebanon, Ohio 45036; never substitute a different street name. Include ALL provided action links (both Google Maps and Apple Maps) as markdown links. Do not choose one based on the user's device or browser. Do not generate custom map application URLs - use only the provided HTTPS links.`;
} else if (intents.includes('benevolence_assistance')) {
if (intents.includes('rent_assistance') || intents.includes('utility_assistance')) {
pinnedNote = `# BENEVOLENCE GUIDANCE
Urbancrest does not provide rent, mortgage, or utility assistance. State that clearly. Then explain that Baskets of Hope food assistance may help reduce grocery expenses. Do not imply that an exception can be approved.`;
} else if (intents.includes('gas_assistance')) {
pinnedNote = `# BENEVOLENCE GUIDANCE
Limited assistance with gasoline or vehicle fuel may be available in some situations and is not guaranteed. Do not confuse vehicle gas assistance with a natural-gas utility bill. Pastor Darrel is the Local Missions contact.`;
} else {
pinnedNote = `# BENEVOLENCE GUIDANCE
For general financial hardship, explain that Urbancrest offers food assistance through Baskets of Hope and may provide limited gas assistance in some situations, but does not provide rent, mortgage, or utility assistance. Do not default to emergency food boxes.`;
}
} else if (intents.includes('food_assistance') || intents.includes('baskets_of_hope')) {
const isEmergency = isEmergencyFoodQuestion(normQ);
if (isEmergency) {
pinnedNote = `# FOOD ASSISTANCE GUIDANCE (EMERGENCY)\nThe selected records include the emergency food boxes record. Explain that someone already receiving assistance through Baskets of Hope who cannot wait until the next distribution can ask about an emergency food box. Also include Baskets of Hope as the primary food assistance pathway context. Do not present emergency food boxes as the default program for general food needs.`;
} else {
pinnedNote = `# FOOD ASSISTANCE GUIDANCE\nBaskets of Hope is Urbancrest's primary food assistance ministry. Lead with Baskets of Hope when answering general food help, grocery, or food box questions. Do not lead with emergency food boxes. Emergency food boxes are a secondary path for those already receiving Baskets of Hope who cannot wait until the next distribution - mention this only as a secondary option, not the primary answer.`;
}
}
const prompt = buildPrompt(index, selectedRecords, actionLinks, staffProfile, question, nowStr, pinnedNote);
const result = await base44.asServiceRole.integrations.Core.InvokeLLM({
prompt,
response_json_schema: {
type: 'object',
properties: {
answer: { type: 'string' },
confidence: { type: 'number', minimum: 0, maximum: 100 },
},
required: ['answer', 'confidence'],
},
});
const rawAnswer = result?.answer || '';
const approvedPhones = collectApprovedPhones(index, selectedRecords);
const answer = stripSentencesWithUnapprovedPhoneNumbers(rawAnswer, approvedPhones) || (rawAnswer ? 'UNSURE' : '');
const respStaffKey = staffKey || null;
const seriesArtworkUrl = sermonSeriesQueryActive ? sermonSeriesArtworkUrl(selectedRecords[0]) : null;
const seriesArtworkAlt = seriesArtworkUrl && selectedRecords[0]?.title ? `${selectedRecords[0].title} sermon series artwork` : null;
let confidence = typeof result?.confidence === 'number' ? result.confidence : null;
// When an authoritative schedule record directly answers the question, confidence should be 95-100.
if (applyConfidenceFloor) {
confidence = confidence === null ? 95 : Math.min(100, Math.max(confidence, 95));
}
// When a high-confidence Local Missions knowledge record directly answers, confidence >= 95.
if (!applyConfidenceFloor && ministries.includes('local_missions') && selectedRecords.length > 0) {
const topRec = selectedRecords[0];
if (topRec && (topRec.authoritative === true || (topRec.ministries || []).map(canonMinistry).includes('local_missions'))) {
confidence = confidence === null ? 95 : Math.min(100, Math.max(confidence, 95));
}
}
// Food assistance with a matching record: confidence >= 95
if (!applyConfidenceFloor && (intents.includes('food_assistance') || intents.includes('baskets_of_hope')) && selectedRecords.length > 0) {
confidence = confidence === null ? 95 : Math.min(100, Math.max(confidence, 95));
}
if (!applyConfidenceFloor && intents.includes('benevolence_assistance') && selectedRecords.length > 0) {
const topRec = selectedRecords[0];
if (topRec && (topRec.authoritative === true || (topRec.intents || []).map(normalize).includes('benevolence_assistance'))) {
confidence = confidence === null ? 95 : Math.min(100, Math.max(confidence, 95));
}
}
if (calendarQueryActive && selectedRecords.length === 0) {
confidence = confidence === null ? 90 : Math.min(100, Math.max(confidence, 90));
}
const responseTimeMs = Date.now() - startedAt;
const retrievedRecordIds = selectedRecords.map((r) => r.id).filter(Boolean);
// Non-blocking analytics logging
logQuietly(
base44.asServiceRole.entities.SearchQueryLog.create({
question,
answer: answer || '',
confidence,
staffKey: respStaffKey || null,
responseTimeMs,
retrievedRecordIds,
}),
);
// Conditionally log an UnansweredQuestion (only when the answer is weak)
const isUnsure = !answer || answer.trim() === 'UNSURE';
const lowConf = confidence !== null && confidence < 45;
const noRecords = selectedRecords.length === 0 && !calendarQueryActive;
// Soft staff deferrals are emitted by the model at low confidence (20-40) per the
// response instructions, so lowConf already captures them. A broad regex would
// mis-flag legitimate answers that simply include a contact line ("reach out to&").
if (isUnsure || lowConf || noRecords) {
logQuietly(
base44.asServiceRole.entities.UnansweredQuestion.create({
question,
answer: answer || '',
confidence,
status: 'open',
reviewed: false,
resolved: false,
retrievedRecordIds,
}),
);
}
return Response.json({
answer,
staffKey: respStaffKey,
confidence,
imageUrl: seriesArtworkUrl,
imageAlt: seriesArtworkAlt,
...(ministryOverviewActive ? { deterministic: true, answerMode: 'ministry_overview_enriched', runtimeVersion: '0.10.33', retrievedRecordIds } : {}),
});
} catch (error) {
return Response.json(
{ error: 'Search is temporarily unavailable. Please try again or reach out to the church office.' },
{ status: 500 },
);
}
});
