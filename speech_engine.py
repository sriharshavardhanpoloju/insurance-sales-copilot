try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False


def get_speech_widget():
    """
    Speech widget that writes transcript directly into Streamlit's
    text_area by finding it in the DOM and dispatching a React change event.
    No copy-paste needed.
    """
    return """
<style>
.sw {
    font-family: 'DM Sans','Inter',sans-serif;
    text-align: center;
    padding: 8px 4px;
}
.sw-status {
    color: #4a6080;
    font-size: 0.76rem;
    margin-bottom: 10px;
    min-height: 16px;
}
#sw-btn {
    background: #3a4add;
    border: none;
    border-radius: 50%;
    width: 58px; height: 58px;
    font-size: 1.4rem;
    cursor: pointer;
    transition: all 0.2s;
    display: block;
    margin: 0 auto 10px;
}
#sw-btn.on {
    background: #c0392b;
    animation: pulse 1.2s infinite;
}
@keyframes pulse {
    0%   { box-shadow: 0 0 0 0    rgba(192,57,43,0.5); }
    70%  { box-shadow: 0 0 0 10px rgba(192,57,43,0);   }
    100% { box-shadow: 0 0 0 0    rgba(192,57,43,0);   }
}
</style>

<div class="sw">
  <div class="sw-status" id="sw-st">Click 🎤 to speak — goes directly to notes box</div>
  <button id="sw-btn" onclick="swToggle()">🎤</button>
</div>

<script>
(function () {
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    var btn = document.getElementById('sw-btn');
    var st  = document.getElementById('sw-st');

    if (!SR) {
        st.textContent = '⚠️ Use Chrome or Edge for speech input';
        btn.disabled = true; btn.style.opacity = '0.4';
        return;
    }

    var rec  = new SR();
    var live = false;
    var full = '';

    rec.continuous     = true;
    rec.interimResults = true;
    rec.lang           = 'en-US';

    // ── Write text into Streamlit's textarea via parent DOM ──
    function pushToStreamlit(text) {
        try {
            var doc = window.parent.document;
            var target = null;

            // Strategy 1: find by data-testid containing our key "notes"
            var byKey = doc.querySelector('[data-testid="stTextArea"] textarea');
            if (byKey) target = byKey;

            // Strategy 2: find by placeholder text
            if (!target) {
                var areas = doc.querySelectorAll('textarea');
                for (var i = 0; i < areas.length; i++) {
                    var ph = areas[i].getAttribute('placeholder') || '';
                    if (ph.indexOf('speak') !== -1 || ph.indexOf('Type') !== -1) {
                        target = areas[i]; break;
                    }
                }
            }

            // Strategy 3: biggest textarea on the page
            if (!target) {
                var areas = doc.querySelectorAll('textarea');
                var maxRows = 0;
                for (var i = 0; i < areas.length; i++) {
                    var r = parseInt(areas[i].getAttribute('rows') || '0');
                    if (r > maxRows) { maxRows = r; target = areas[i]; }
                }
            }

            if (target) {
                // Trigger React synthetic event so Streamlit state updates
                var setter = Object.getOwnPropertyDescriptor(
                    window.parent.HTMLTextAreaElement.prototype, 'value'
                ).set;
                setter.call(target, text);
                target.dispatchEvent(new window.parent.Event('input',  { bubbles: true }));
                target.dispatchEvent(new window.parent.Event('change', { bubbles: true }));
                target.focus();
            }
        } catch (e) {
            window.parent.postMessage({ type: 'speech_transcript', value: text }, '*');
        }
    }

    rec.onresult = function (e) {
        var interim = '';
        for (var i = e.resultIndex; i < e.results.length; i++) {
            if (e.results[i].isFinal) full += e.results[i][0].transcript + ' ';
            else interim += e.results[i][0].transcript;
        }
        pushToStreamlit((full + interim).trim());
    };

    rec.onerror = function (e) {
        st.textContent = '⚠️ Mic error: ' + e.error;
        swStop();
    };

    rec.onend = function () {
        if (live) { try { rec.start(); } catch (x) {} }
    };

    function swStart() {
        full = '';
        try {
            rec.start(); live = true;
            btn.innerHTML = '⏹'; btn.classList.add('on');
            st.textContent = '🔴 Recording — speak now, click ⏹ to stop';
            st.style.color = '#c06060';
        } catch (x) {
            st.textContent = 'Could not start mic: ' + x.message;
        }
    }

    function swStop() {
        live = false;
        try { rec.stop(); } catch (x) {}
        btn.innerHTML = '🎤'; btn.classList.remove('on');
        st.textContent = '✅ Done — text sent to notes box';
        st.style.color = '#50c878';
        pushToStreamlit(full.trim());
    }

    window.swToggle = function () { live ? swStop() : swStart(); };
})();
</script>
"""


def record_and_transcribe(duration_seconds=10):
    if not SR_AVAILABLE:
        return ""
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=duration_seconds)
        return recognizer.recognize_google(audio)
    except Exception:
        return ""
