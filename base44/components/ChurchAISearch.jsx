import { useEffect, useRef, useState } from 'react';
import { base44 } from '@/api/base44Client';
import { Search, Loader2, X, MessageCircle, ChevronDown, Phone, Mail } from 'lucide-react';
import MarkdownAnswer from '@/components/church/MarkdownAnswer';
import StaffModal from '@/components/church/StaffModal';

const SEARCH_CLIENT_ID_KEY = 'urbancrest_search_client_id';
const SEARCH_CACHE_MS = 10_000;
const MAX_QUESTION_LENGTH = 500;

function getOrCreateSearchClientId() {
  try {
    const existing = window.localStorage.getItem(SEARCH_CLIENT_ID_KEY);
    if (existing) return existing;
    const next = window.crypto?.randomUUID?.() || `uc-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    window.localStorage.setItem(SEARCH_CLIENT_ID_KEY, next);
    return next;
  } catch {
    return `uc-session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }
}

function normalizedCacheKey(value) {
  return String(value || '').trim().toLowerCase().replace(/\s+/g, ' ');
}

function ensureTurnstileScript() {
  if (window.turnstile) return Promise.resolve(window.turnstile);
  if (window.__urbancrestTurnstilePromise) return window.__urbancrestTurnstilePromise;

  window.__urbancrestTurnstilePromise = new Promise((resolve, reject) => {
    const existing = document.querySelector('script[data-urbancrest-turnstile="true"]');
    if (existing) {
      const started = Date.now();
      const waitForApi = () => {
        if (window.turnstile) return resolve(window.turnstile);
        if (Date.now() - started > 10_000) return reject(new Error('Turnstile did not load.'));
        window.setTimeout(waitForApi, 50);
      };
      waitForApi();
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    script.async = true;
    script.defer = true;
    script.dataset.urbancrestTurnstile = 'true';
    script.onload = () => {
      if (window.turnstile) resolve(window.turnstile);
      else reject(new Error('Turnstile loaded without an API.'));
    };
    script.onerror = () => reject(new Error('Turnstile could not load.'));
    document.head.appendChild(script);
  });

  return window.__urbancrestTurnstilePromise;
}

export default function ChurchAISearch() {
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const [staffExpanded, setStaffExpanded] = useState(false);
  const [modalStaff, setModalStaff] = useState(null);
  const [staffCardRect, setStaffCardRect] = useState(null);
  const [staffByKey, setStaffByKey] = useState({});
  const [status, setStatus] = useState(null);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const [cooldownSeconds, setCooldownSeconds] = useState(0);
  const [verificationActive, setVerificationActive] = useState(false);

  const staffCardRef = useRef(null);
  const inputRef = useRef(null);
  const answerRef = useRef(null);
  const activeRequestRef = useRef(0);
  const clientIdRef = useRef(null);
  const turnstileContainerRef = useRef(null);
  const turnstileWidgetRef = useRef(null);
  const lastSuccessfulSearchRef = useRef(null);

  const getStaffByKey = (key) => (key ? staffByKey[key] || null : null);

  const loadStaffByKey = async (key) => {
    if (!key || staffByKey[key]) return;

    try {
      const matches = await base44.entities.Staff.filter({ key }, '-order', 1);
      const staff = Array.isArray(matches) ? matches[0] : null;
      if (staff) {
        setStaffByKey((current) => ({ ...current, [key]: staff }));
        return;
      }
    } catch {
      // Fall back to the existing list API if filtered reads are unavailable.
    }

    try {
      const list = await base44.entities.Staff.list('-order', 100);
      const staff = list.find((person) => person.key === key);
      if (staff) setStaffByKey((current) => ({ ...current, [key]: staff }));
    } catch {
      // The answer can still render without the optional staff card.
    }
  };

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => setIsVisible(entry.isIntersecting),
      { threshold: 0.1 },
    );

    if (inputRef.current) observer.observe(inputRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!cooldownUntil) {
      setCooldownSeconds(0);
      return undefined;
    }

    const update = () => {
      const seconds = Math.max(0, Math.ceil((cooldownUntil - Date.now()) / 1000));
      setCooldownSeconds(seconds);
      if (seconds <= 0) {
        setCooldownUntil(0);
        setStatus((current) => (current?.code === 'rate_limit' ? null : current));
      }
    };

    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [cooldownUntil]);

  useEffect(() => () => {
    if (turnstileWidgetRef.current !== null && window.turnstile) {
      try { window.turnstile.remove(turnstileWidgetRef.current); } catch { /* ignore */ }
    }
  }, []);

  const suggestions = [
    'What time are Sunday services?',
    'How do I get to the church?',
    'What upcoming events are happening?',
    'What does Urbancrest believe about salvation?',
  ];

  const removeTurnstileWidget = () => {
    if (turnstileWidgetRef.current !== null && window.turnstile) {
      try { window.turnstile.remove(turnstileWidgetRef.current); } catch { /* ignore */ }
    }
    turnstileWidgetRef.current = null;
    if (turnstileContainerRef.current) turnstileContainerRef.current.innerHTML = '';
    setVerificationActive(false);
  };

  const requestTurnstileToken = async (siteKey, action = 'ai_search') => {
    if (!siteKey) throw new Error('Verification is not configured.');
    setVerificationActive(true);
    setStatus({ code: 'verifying', tone: 'info', text: 'Verifying your request…' });

    const turnstile = await ensureTurnstileScript();
    const container = turnstileContainerRef.current;
    if (!container) throw new Error('Verification area is unavailable.');

    if (turnstileWidgetRef.current !== null) {
      try { turnstile.remove(turnstileWidgetRef.current); } catch { /* ignore */ }
      turnstileWidgetRef.current = null;
    }
    container.innerHTML = '';

    return new Promise((resolve, reject) => {
      let settled = false;
      const fail = (message) => {
        if (settled) return true;
        settled = true;
        reject(new Error(message));
        return true;
      };

      const widgetId = turnstile.render(container, {
        sitekey: siteKey,
        action,
        theme: 'auto',
        appearance: 'interaction-only',
        execution: 'execute',
        callback: (token) => {
          if (settled) return;
          settled = true;
          resolve(token);
        },
        'error-callback': () => fail('Verification failed.'),
        'expired-callback': () => fail('Verification expired.'),
        'timeout-callback': () => fail('Verification timed out.'),
      });

      turnstileWidgetRef.current = widgetId;
      turnstile.execute(widgetId);
    });
  };

  const applyResponse = (data, searchQuery) => {
    const answerText = data?.answer || '';
    const staffKey = data?.staffKey || null;
    const imageUrl = data?.imageUrl || null;
    const imageAlt = data?.imageAlt || '';
    const isUnsure = !answerText || answerText.trim() === 'UNSURE';

    if (isUnsure) {
      setAnswer({ type: 'unsure', text: null, staffKey: null, imageUrl: null, imageAlt: '' });
      return;
    }

    const nextAnswer = {
      type: 'answer',
      text: answerText,
      staffKey,
      answerMode: data?.answerMode || null,
      directAnswerType: data?.directAnswerType || null,
      imageUrl,
      imageAlt,
    };
    setAnswer(nextAnswer);
    if (staffKey) void loadStaffByKey(staffKey);

    lastSuccessfulSearchRef.current = {
      key: normalizedCacheKey(searchQuery),
      at: Date.now(),
      data,
    };
  };

  const invokeSearch = async (searchQuery, turnstileToken = '') => {
    if (!clientIdRef.current) clientIdRef.current = getOrCreateSearchClientId();
    const response = await base44.functions.invoke('queryKnowledgeBase', {
      question: searchQuery,
      clientId: clientIdRef.current,
      ...(turnstileToken ? { turnstileToken } : {}),
    });
    return response?.data || {};
  };

  const handleSearch = async (q) => {
    const searchQuery = (q || query).trim();
    if (!searchQuery || loading || cooldownSeconds > 0) return;

    if (searchQuery.length > MAX_QUESTION_LENGTH) {
      setStatus({
        code: 'too_long',
        tone: 'warning',
        text: `Please shorten your question to ${MAX_QUESTION_LENGTH} characters or fewer.`,
      });
      return;
    }

    const cacheKey = normalizedCacheKey(searchQuery);
    const cached = lastSuccessfulSearchRef.current;
    if (cached && cached.key === cacheKey && Date.now() - cached.at < SEARCH_CACHE_MS) {
      setQuery(searchQuery);
      setExpanded(true);
      setStatus(null);
      applyResponse(cached.data, searchQuery);
      window.setTimeout(
        () => answerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }),
        50,
      );
      return;
    }

    const requestId = ++activeRequestRef.current;

    setQuery(searchQuery);
    setLoading(true);
    setAnswer(null);
    setExpanded(true);
    setStatus(null);
    setStaffExpanded(false);
    setModalStaff(null);
    setStaffCardRect(null);

    try {
      let data = await invokeSearch(searchQuery);
      if (requestId !== activeRequestRef.current) return;

      if (data?.rateLimited) {
        const seconds = Math.max(1, Number(data.retryAfterSeconds || 1));
        setCooldownUntil(Date.now() + seconds * 1000);
        setStatus({
          code: 'rate_limit',
          tone: 'warning',
          text: data.message || `You've sent several searches pretty quickly. Please try again in ${seconds} seconds.`,
        });
        return;
      }

      if (data?.verificationRequired) {
        const token = await requestTurnstileToken(data.turnstileSiteKey, data.verificationAction || 'ai_search');
        if (requestId !== activeRequestRef.current) return;
        data = await invokeSearch(searchQuery, token);
        removeTurnstileWidget();
        if (requestId !== activeRequestRef.current) return;
      }

      if (data?.rateLimited) {
        const seconds = Math.max(1, Number(data.retryAfterSeconds || 1));
        setCooldownUntil(Date.now() + seconds * 1000);
        setStatus({
          code: 'rate_limit',
          tone: 'warning',
          text: data.message || `You've sent several searches pretty quickly. Please try again in ${seconds} seconds.`,
        });
        return;
      }

      if (data?.verificationFailed) {
        setStatus({
          code: 'verification_failed',
          tone: 'error',
          text: data.message || 'We could not verify your request. Please try again.',
        });
        return;
      }

      if (data?.error) throw new Error(data.error);

      setStatus(null);
      applyResponse(data, searchQuery);
    } catch {
      if (requestId === activeRequestRef.current) {
        removeTurnstileWidget();
        setStatus({
          code: 'search_error',
          tone: 'error',
          text: 'Search is temporarily unavailable. Your question is still here, so you can try again.',
        });
      }
    } finally {
      if (requestId === activeRequestRef.current) {
        setLoading(false);
        setVerificationActive(false);
        window.setTimeout(
          () => answerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }),
          100,
        );
      }
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !loading && cooldownSeconds <= 0) handleSearch();
  };

  const handleClear = () => {
    activeRequestRef.current += 1;
    removeTurnstileWidget();
    setQuery('');
    setAnswer(null);
    setExpanded(false);
    setLoading(false);
    setStatus(null);
    setStaffExpanded(false);
    setModalStaff(null);
    setStaffCardRect(null);
    inputRef.current?.focus();
  };

  const answerStaff = answer?.staffKey ? getStaffByKey(answer.staffKey) : null;
  const hasStaffContact = Boolean(answerStaff?.phone || answerStaff?.email);
  const searchDisabled = loading || cooldownSeconds > 0 || !query.trim();

  const openStaffModal = () => {
    if (!answerStaff) return;
    const rect = staffCardRef.current?.getBoundingClientRect();
    if (rect) {
      setStaffCardRect({
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
      });
    }
    setModalStaff(answerStaff);
  };

  return (
    <section className="relative px-4 sm:px-6 lg:px-8 pt-40 pb-40 overflow-hidden">
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full opacity-[0.06] animate-god-ray pointer-events-none"
        style={{
          background: 'radial-gradient(circle, rgba(3,184,66,0.85) 0%, transparent 70%)',
        }}
      />

      <div className="relative max-w-2xl mx-auto">
        <div className="flex items-center justify-center gap-2 mb-4">
          <MessageCircle className="w-4 h-4 text-primary" />
          <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Ask Anything
          </span>
        </div>

        <div className="relative flex items-center glass rounded-2xl border border-border shadow-sm focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/20 transition-all">
          <Search className="absolute left-4 w-4 h-4 text-muted-foreground shrink-0 pointer-events-none" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            maxLength={MAX_QUESTION_LENGTH}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about services, events, faith, sermons…"
            className={`flex-1 bg-transparent text-foreground placeholder:text-muted-foreground text-base sm:text-sm px-10 py-4 outline-none truncate ${isVisible ? 'animate-scroll-placeholder' : ''}`}
            style={{ paddingRight: '130px' }}
            aria-label="Ask Urbancrest a question"
          />

          {query && (
            <button
              type="button"
              onClick={handleClear}
              className="absolute right-20 p-1 text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Clear search"
            >
              <X className="w-4 h-4" />
            </button>
          )}

          <button
            type="button"
            onClick={() => handleSearch()}
            disabled={searchDisabled}
            className="absolute right-3 px-3 py-1.5 rounded-xl bg-primary text-primary-foreground text-xs font-semibold disabled:opacity-40 hover:bg-[#02a63a] transition-colors"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : cooldownSeconds > 0 ? `${cooldownSeconds}s` : 'Ask'}
          </button>
        </div>

        {status && (
          <div
            className={`mt-3 rounded-xl border px-4 py-3 text-sm ${
              status.tone === 'error'
                ? 'border-red-500/25 bg-red-500/5 text-red-300'
                : status.tone === 'warning'
                  ? 'border-amber-500/25 bg-amber-500/5 text-amber-200'
                  : 'border-border bg-secondary/40 text-muted-foreground'
            }`}
            role={status.tone === 'error' ? 'alert' : 'status'}
            aria-live="polite"
          >
            {status.code === 'rate_limit' && cooldownSeconds > 0
              ? status.text.replace(/\d+\s+seconds?\.?$/i, `${cooldownSeconds} seconds.`)
              : status.text}
          </div>
        )}

        <div
          ref={turnstileContainerRef}
          className={`${verificationActive ? 'mt-3' : ''} flex justify-center`}
          aria-live="polite"
        />

        {!expanded && (
          <div className="flex flex-wrap gap-2 mt-3 justify-center">
            {suggestions.map((suggestion) => (
              <button
                type="button"
                key={suggestion}
                onClick={() => handleSearch(suggestion)}
                disabled={loading || cooldownSeconds > 0}
                className="text-xs px-3 py-1.5 rounded-full bg-secondary border border-border text-muted-foreground hover:text-foreground hover:border-primary/40 transition-all disabled:opacity-40"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}

        {(loading || answer) && (
          <div ref={answerRef} className="mt-4 glass rounded-2xl border border-border overflow-hidden">
            {loading && (
              <div className="flex items-center gap-3 px-5 py-5 text-muted-foreground text-sm">
                <Loader2 className="w-4 h-4 animate-spin text-primary shrink-0" />
                {status?.code === 'verifying' ? 'Verifying your request…' : 'Searching Urbancrest…'}
              </div>
            )}

            {!loading && answer?.type === 'answer' && (
              <div className="px-5 py-5">
                {answerStaff && (
                  <div
                    ref={staffCardRef}
                    className="mb-4 flex items-center gap-3 p-3 rounded-xl bg-secondary/50 border border-border hover:border-primary/40 transition-colors"
                  >
                    <button
                      type="button"
                      onClick={openStaffModal}
                      className="flex items-center gap-3 flex-1 min-w-0 text-left"
                    >
                      {answerStaff.photo ? (
                        <img
                          src={answerStaff.photo}
                          alt={answerStaff.name}
                          className={`rounded-full object-cover object-top shrink-0 transition-all duration-200 ${staffExpanded ? 'w-20 h-20' : 'w-14 h-14'}`}
                        />
                      ) : (
                        <div
                          className={`rounded-full bg-primary/10 flex items-center justify-center shrink-0 transition-all duration-200 ${staffExpanded ? 'w-20 h-20' : 'w-14 h-14'}`}
                        >
                          <span className="text-primary font-bold text-sm">
                            {(answerStaff.name || '')
                              .split(' ')
                              .filter(Boolean)
                              .map((name) => name[0])
                              .join('')}
                          </span>
                        </div>
                      )}

                      <div className="min-w-0">
                        <p
                          className={`font-semibold text-foreground transition-all duration-200 ${staffExpanded ? 'text-base' : 'text-sm'}`}
                        >
                          {staffExpanded
                            ? answerStaff.name
                            : answerStaff.label || answerStaff.name}
                        </p>
                        <p
                          className={`text-muted-foreground transition-all duration-200 ${staffExpanded ? 'text-sm' : 'text-xs'}`}
                        >
                          {answerStaff.role}
                        </p>
                      </div>
                    </button>

                    {hasStaffContact && (
                      <div className="flex items-center gap-2 shrink-0">
                        {staffExpanded ? (
                          <>
                            {answerStaff.phone && (
                              <a
                                href={`tel:${answerStaff.phone}`}
                                className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-background border border-border text-muted-foreground hover:text-primary hover:border-primary/40 transition-colors"
                                aria-label={`Call ${answerStaff.name}`}
                                onClick={(event) => event.stopPropagation()}
                              >
                                <Phone className="w-4 h-4" />
                              </a>
                            )}
                            {answerStaff.email && (
                              <a
                                href={`mailto:${answerStaff.email}`}
                                className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-background border border-border text-muted-foreground hover:text-primary hover:border-primary/40 transition-colors"
                                aria-label={`Email ${answerStaff.name}`}
                                onClick={(event) => event.stopPropagation()}
                              >
                                <Mail className="w-4 h-4" />
                              </a>
                            )}
                          </>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setStaffExpanded((value) => !value)}
                            aria-label="Show contact options"
                            className="p-1 text-muted-foreground hover:text-foreground transition-colors"
                          >
                            <ChevronDown className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {answer.imageUrl && (
                  <div className="mb-4 overflow-hidden rounded-xl border border-border bg-secondary/30">
                    <img
                      src={answer.imageUrl}
                      alt={answer.imageAlt || 'Sermon series artwork'}
                      className="block w-full h-auto"
                      loading="lazy"
                      onError={(event) => {
                        event.currentTarget.style.display = 'none';
                      }}
                    />
                  </div>
                )}

                <MarkdownAnswer>{answer.text}</MarkdownAnswer>

                <p className="text-[10px] text-muted-foreground mt-4 pt-3 border-t border-border">
                  Answers are based on Urbancrest information and may occasionally be incomplete or outdated. For personal questions, speak with one of our{' '}
                  <a href="/staff" className="text-primary hover:underline">
                    pastors or staff
                  </a>.
                </p>
              </div>
            )}

            {!loading && answer?.type === 'unsure' && (
              <div className="px-5 py-5">
                <p className="text-foreground text-sm leading-relaxed">
                  This search feature is still in development and may not have an answer for every question. It can also make mistakes. For the best answer, we'd love to connect you with one of our{' '}
                  <a href="/staff" className="text-primary hover:underline font-semibold">
                    pastors or church staff
                  </a>{' '}
                  who would be happy to help.
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {modalStaff && (
        <StaffModal
          person={modalStaff}
          cardRect={staffCardRect}
          onClose={() => setModalStaff(null)}
        />
      )}
    </section>
  );
}
