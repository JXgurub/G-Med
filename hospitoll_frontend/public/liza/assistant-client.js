$(document).ready(function () {
    var installPrompt = null;
    var isListening = false;
    var recordingStream = null;
    var audioContext = null;
    var audioSource = null;
    var audioProcessor = null;
    var recordingSampleRate = 16000;
    var audioFrames = [];
    var utteranceSamples = 0;
    var voicedSamples = 0;
    var lastVoiceAt = 0;
    var isProcessingVoice = false;
    var isSpeaking = false;
    var speakingToken = 0;
    var stopAfterCurrentReply = false;
    var youtubePlayer = null;
    var youtubeApiPromise = null;
    var youtubeFrameId = 0;
    var activeYoutubeBubble = null;
    var youtubeVolumeBeforeListening = null;
    var youtubeDuckTimeout = null;
    var youtubeDuckPending = false;
    var internetSearchStorageKey = "gmed_liza_internet_search";
    var internetSearchToggle = document.getElementById("InternetSearchToggle");
    var apiUrlMeta = document.querySelector('meta[name="liza-api-url"]');
    var commandUrl = apiUrlMeta ? apiUrlMeta.content : "/api/liza/command/";
    var apiBaseUrl = commandUrl.replace(/command\/?$/, "");

    function isInternetSearchEnabled() {
        return localStorage.getItem(internetSearchStorageKey) === "true";
    }

    function updateInternetSearchToggle() {
        if (!internetSearchToggle) return;
        var enabled = isInternetSearchEnabled();
        internetSearchToggle.setAttribute("aria-checked", String(enabled));
        var privacyNotice = document.getElementById("InternetSearchPrivacy");
        if (privacyNotice) privacyNotice.hidden = !enabled;
        internetSearchToggle.setAttribute(
            "aria-label",
            "Internet orqali qidirish " + (enabled ? "yoqilgan" : "o‘chiq")
        );
    }

    function setNativeAudioPlayback(active) {
        var bridge = window.LizaNativeAudio;
        if (!bridge || typeof bridge.postMessage !== "function") return false;
        bridge.onmessage = function (event) {
            if (event.data === "speaker-unavailable") {
                setStatus("Telefon karnayini yoqib bo‘lmadi. Ovoz chiqish qurilmasini telefon sozlamasidan tanlang.");
            }
        };
        bridge.postMessage(JSON.stringify({ action: "playback", active: Boolean(active) }));
        return true;
    }

    if (window.SiriWave) {
        new SiriWave({
            container: document.getElementById("siri-container"),
            width: Math.max(280, Math.min(window.innerWidth - 32, 800)),
            height: 160,
            style: "ios9",
            amplitude: 1,
            speed: 0.3,
            autostart: true
        });
    }

    function showAssistant() {
        $("#Oval").prop("hidden", false);
        $("#SiriWave").attr("hidden", false);
        document.body.classList.add("liza-listening");
    }

    function setStatus(message) {
        $(".siri-message").text(message);
    }

    function appendTextWithLinks(element, message) {
        var text = String(message || "");
        var urlPattern = /https?:\/\/[^\s<>"']+/g;
        var cursor = 0;
        var match;
        while ((match = urlPattern.exec(text))) {
            var url = match[0].replace(/[.,!?;:)]+$/, "");
            if (!url) continue;
            element.appendChild(document.createTextNode(text.slice(cursor, match.index)));
            var link = document.createElement("a");
            link.href = url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = url;
            link.className = "internet-search-result-link";
            element.appendChild(link);
            cursor = match.index + url.length;
            urlPattern.lastIndex = cursor;
        }
        element.appendChild(document.createTextNode(text.slice(cursor)));
    }

    function loadYoutubeApi() {
        if (window.YT && window.YT.Player) return Promise.resolve(window.YT);
        if (youtubeApiPromise) return youtubeApiPromise;
        youtubeApiPromise = new Promise(function (resolve) {
            window.onYouTubeIframeAPIReady = function () { resolve(window.YT); };
            var script = document.createElement("script");
            script.src = "https://www.youtube.com/iframe_api";
            document.head.appendChild(script);
        });
        return youtubeApiPromise;
    }

    function mountYoutubePlayer(iframe) {
        loadYoutubeApi().then(function (api) {
            if (!iframe.isConnected) return;
            youtubePlayer = new api.Player(iframe.id, {
                events: {
                    onReady: function (event) {
                        if (typeof event.target.setVolume === "function") event.target.setVolume(100);
                        event.target.playVideo();
                        if (youtubeDuckPending || youtubeVolumeBeforeListening !== null) duckYoutubeVolume();
                    },
                    onStateChange: function (event) {
                        if (event.data === api.PlayerState.PLAYING) {
                            var nativeRoute = setNativeAudioPlayback(true);
                            setStatus(nativeRoute
                                ? "Qo‘shiq telefon karnayida ijro etilmoqda."
                                : "Brauzer karnayni boshqara olmaydi. Telefon karnayini tanlash uchun G-MED Liza Android ilovasidan foydalaning.");
                        } else if (event.data === api.PlayerState.PAUSED || event.data === api.PlayerState.ENDED) {
                            setNativeAudioPlayback(false);
                        }
                    },
                    onError: function () {
                        setNativeAudioPlayback(false);
                        setStatus("Bu videoni pleyerda ijro qilib bo‘lmadi. YouTube’da ochish havolasini bosing.");
                    }
                }
            });
        });
    }

    function duckYoutubeVolume() {
        if (!youtubePlayer || typeof youtubePlayer.getVolume !== "function" || typeof youtubePlayer.setVolume !== "function") {
            youtubeDuckPending = true;
            return;
        }
        youtubeDuckPending = false;
        if (youtubeVolumeBeforeListening === null) youtubeVolumeBeforeListening = youtubePlayer.getVolume();
        youtubePlayer.setVolume(Math.min(youtubeVolumeBeforeListening, 15));
        window.clearTimeout(youtubeDuckTimeout);
        youtubeDuckTimeout = window.setTimeout(restoreYoutubeVolume, 8000);
    }

    function restoreYoutubeVolume() {
        window.clearTimeout(youtubeDuckTimeout);
        youtubeDuckTimeout = null;
        youtubeDuckPending = false;
        if (youtubeVolumeBeforeListening === null) return;
        if (youtubePlayer && typeof youtubePlayer.setVolume === "function") youtubePlayer.setVolume(youtubeVolumeBeforeListening);
        youtubeVolumeBeforeListening = null;
    }

    function stopActiveYoutubePlayer() {
        setNativeAudioPlayback(false);
        restoreYoutubeVolume();
        if (youtubePlayer) {
            try {
                youtubePlayer.stopVideo();
                youtubePlayer.destroy();
            } catch (error) {
                console.warn("YouTube pleyerini to'xtatib bo'lmadi.");
            }
            youtubePlayer = null;
        }
        document.querySelectorAll("iframe.youtube-player").forEach(function (iframe) {
            iframe.remove();
        });
        activeYoutubeBubble = null;
    }

    function appendMessage(message, role, videoId) {
        var chatBox = document.getElementById("chat-canvas-body");
        if (!chatBox || !message) return;

        if (videoId && /^[\w-]{11}$/.test(videoId)) stopActiveYoutubePlayer();

        var row = document.createElement("div");
        var width = document.createElement("div");
        var bubble = document.createElement("div");
        row.className = "row justify-content-" + (role === "sender" ? "end" : "start") + " mb-3";
        width.className = "width-size";
        bubble.className = role + "_message";
        if (videoId && /^[\w-]{11}$/.test(videoId)) {
            var trackTitle = document.createElement("div");
            trackTitle.className = "youtube-track-title";
            trackTitle.textContent = message;
            bubble.appendChild(trackTitle);
            var player = document.createElement("iframe");
            youtubeFrameId += 1;
            player.id = "liza-youtube-player-" + youtubeFrameId;
            player.className = "youtube-player";
            player.title = "YouTube qo‘shiq ijrosi";
            player.src = "https://www.youtube.com/embed/" + videoId + "?autoplay=1&playsinline=1&controls=1&rel=0&enablejsapi=1&origin=" + encodeURIComponent(window.location.origin);
            player.referrerPolicy = "strict-origin-when-cross-origin";
            player.allow = "autoplay; encrypted-media; picture-in-picture";
            player.allowFullscreen = true;
            bubble.appendChild(player);

            var fallbackLink = document.createElement("a");
            fallbackLink.className = "youtube-fallback-link";
            fallbackLink.href = "https://www.youtube.com/watch?v=" + videoId;
            fallbackLink.target = "_blank";
            fallbackLink.rel = "noopener noreferrer";
            fallbackLink.textContent = "Pleyer xato bersa, YouTube’da ochish";
            bubble.appendChild(fallbackLink);
            activeYoutubeBubble = bubble;
            mountYoutubePlayer(player);
        } else {
            appendTextWithLinks(bubble, message);
        }
        width.appendChild(bubble);
        row.appendChild(width);
        chatBox.appendChild(row);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function authHeaders() {
        var role = sessionStorage.getItem("user_role") || localStorage.getItem("user_role");
        var token = role === "doctor"
            ? sessionStorage.getItem("doctor_access_token")
            : localStorage.getItem("access_token");
        if (!token) throw new Error("Avval G-MED hisobingizga kiring.");
        return { "Authorization": "Bearer " + token };
    }

    async function speakMadina(text, onEnded) {
        var token = ++speakingToken;
        isSpeaking = true;
        var audioUrl = null;
        try {
            var headers = authHeaders();
            headers["Content-Type"] = "application/json";
            var response = await fetch(apiBaseUrl + "speech/", {
                method: "POST",
                credentials: "same-origin",
                headers: headers,
                body: JSON.stringify({ text: text })
            });
            var data = await response.json().catch(function () { return {}; });
            if (!response.ok) throw new Error(data.error || "Madina ovozini yaratib bo'lmadi.");

            var bytes = Uint8Array.from(atob(data.audio), function (character) { return character.charCodeAt(0); });
            audioUrl = URL.createObjectURL(new Blob([bytes], { type: data.content_type || "audio/mpeg" }));
            var player = new Audio(audioUrl);
            await new Promise(function (resolve, reject) {
                player.onended = resolve;
                player.onerror = function () { reject(new Error("Madina ovozi ijro etilmadi.")); };
                player.play().catch(reject);
            });
            if (token === speakingToken && onEnded) onEnded();
        } catch (error) {
            setStatus(error.message || "Madina ovozini ijro etib bo'lmadi.");
            if (token === speakingToken && stopAfterCurrentReply) stopRecording(false);
        } finally {
            if (audioUrl) URL.revokeObjectURL(audioUrl);
            if (token === speakingToken) {
                isSpeaking = false;
                if (stopAfterCurrentReply) {
                    stopAfterCurrentReply = false;
                    stopRecording(false);
                }
            }
        }
    }

    function showReply(data) {
        if (data.transcript) appendMessage(data.transcript, "sender");
        if (data.reply) {
            if (data.action === "youtube_duck") {
                appendMessage(data.reply, "receiver");
                duckYoutubeVolume();
                setStatus("Musiqa pasaydi. Buyruqni ayting.");
                return;
            }
            appendMessage(data.reply, "receiver", data.action === "play_youtube" ? data.video_id : null);
            setStatus(data.reply);
            if (data.action === "play_youtube") {
                var chatCanvas = document.getElementById("offcanvasScrolling");
                if (chatCanvas && window.bootstrap && window.bootstrap.Offcanvas) {
                    window.bootstrap.Offcanvas.getOrCreateInstance(chatCanvas).show();
                }
                setStatus("YouTube pleyeri tayyor. Avtoijro bloklansa, pleyerdagi ijro tugmasini bosing.");
                return;
            }
            if (data.action === "youtube_control") {
                if (data.control === "next" || data.control === "previous") {
                    if (activeYoutubeBubble) {
                        var trackTitle = activeYoutubeBubble.querySelector(".youtube-track-title");
                        var fallbackLink = activeYoutubeBubble.querySelector(".youtube-fallback-link");
                        if (trackTitle) trackTitle.textContent = "YouTube’da “" + data.video_title + "” qo‘shig‘ini ijro etyapman.";
                        if (fallbackLink) fallbackLink.href = "https://www.youtube.com/watch?v=" + data.video_id;
                    }
                    if (youtubePlayer && typeof youtubePlayer.loadVideoById === "function") {
                        youtubePlayer.loadVideoById(data.video_id);
                    } else if (activeYoutubeBubble) {
                        var existingPlayer = activeYoutubeBubble.querySelector("iframe.youtube-player");
                        if (existingPlayer) existingPlayer.src = "https://www.youtube.com/embed/" + data.video_id + "?autoplay=1&playsinline=1&rel=0&enablejsapi=1&origin=" + encodeURIComponent(window.location.origin);
                    }
                } else if (youtubePlayer) {
                    if (data.control === "pause") youtubePlayer.pauseVideo();
                    if (data.control === "play") youtubePlayer.playVideo();
                    if (data.control === "rewind") youtubePlayer.seekTo(Math.max(0, youtubePlayer.getCurrentTime() - 10), true);
                }
                restoreYoutubeVolume();
                setStatus(data.reply);
                return;
            }
            restoreYoutubeVolume();
            stopAfterCurrentReply = data.action === "stop_listening";
            var afterReply;
            if (data.action === "open_profile") {
                afterReply = function () {
                    window.location.assign("/patient?tab=profile");
                };
            } else if (data.action === "open_booking") {
                afterReply = function () {
                    if (!data.booking || !data.booking.clinic_id || !data.booking.doctor_id) {
                        setStatus("Qabul oynasini ochish ma’lumoti topilmadi. Doktorni qayta tanlang.");
                        return;
                    }
                    var params = new URLSearchParams({
                        lizaDoctor: data.booking.doctor_id,
                        lizaSpecialtyPriceIds: (data.booking.specialty_price_ids || []).join(",")
                    });
                    window.location.assign("/clinic/" + encodeURIComponent(data.booking.clinic_id) + "?" + params.toString());
                };
            } else {
                afterReply = function () {
                    if (isListening && !stopAfterCurrentReply) setStatus("Tinglayapman. Davom eting yoki mikrofonni bosing.");
                };
            }
            var spokenReply = data.reply.split("\nManbalar:\n")[0];
            speakMadina(spokenReply, afterReply);
        }
    }

    function createWavBlob(frames, inputRate) {
        var inputLength = frames.reduce(function (total, frame) { return total + frame.length; }, 0);
        if (!inputLength) return null;
        var input = new Float32Array(inputLength);
        var offset = 0;
        frames.forEach(function (frame) {
            input.set(frame, offset);
            offset += frame.length;
        });

        var outputRate = 16000;
        var outputLength = Math.round(input.length * outputRate / inputRate);
        var pcm = new Int16Array(outputLength);
        for (var index = 0; index < outputLength; index += 1) {
            var sourceIndex = index * inputRate / outputRate;
            var left = Math.floor(sourceIndex);
            var right = Math.min(left + 1, input.length - 1);
            var fraction = sourceIndex - left;
            var sample = input[left] * (1 - fraction) + input[right] * fraction;
            pcm[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
        }

        var buffer = new ArrayBuffer(44 + pcm.length * 2);
        var view = new DataView(buffer);
        function writeText(position, text) {
            for (var charIndex = 0; charIndex < text.length; charIndex += 1) {
                view.setUint8(position + charIndex, text.charCodeAt(charIndex));
            }
        }
        writeText(0, "RIFF");
        view.setUint32(4, 36 + pcm.length * 2, true);
        writeText(8, "WAVE");
        writeText(12, "fmt ");
        view.setUint32(16, 16, true);
        view.setUint16(20, 1, true);
        view.setUint16(22, 1, true);
        view.setUint32(24, outputRate, true);
        view.setUint32(28, outputRate * 2, true);
        view.setUint16(32, 2, true);
        view.setUint16(34, 16, true);
        writeText(36, "data");
        view.setUint32(40, pcm.length * 2, true);
        for (var sampleIndex = 0; sampleIndex < pcm.length; sampleIndex += 1) {
            view.setInt16(44 + sampleIndex * 2, pcm[sampleIndex], true);
        }
        return new Blob([buffer], { type: "audio/wav" });
    }

    function resetUtterance() {
        audioFrames = [];
        utteranceSamples = 0;
        voicedSamples = 0;
        lastVoiceAt = 0;
    }

    function submitCurrentUtterance() {
        if (!isListening || isSpeaking || isProcessingVoice || !utteranceSamples) return;
        if (voicedSamples < recordingSampleRate * 0.25) {
            resetUtterance();
            return;
        }
        var blob = createWavBlob(audioFrames, recordingSampleRate);
        resetUtterance();
        if (!blob) return;

        isProcessingVoice = true;
        setStatus("Buyruqni tushunib, javob tayyorlayapman...");
        sendVoiceToDjango(blob, "audio/wav")
            .catch(function (error) { setStatus(error.message || "Ovoz serverda qayta ishlanmadi."); })
            .finally(function () {
                isProcessingVoice = false;
                if (isListening && !isSpeaking) setStatus("Tinglayapman. Davom eting yoki mikrofonni bosing.");
            });
    }

    function stopRecording(submitPending) {
        if (!isListening) return;
        isListening = false;
        restoreYoutubeVolume();
        if (audioProcessor) {
            audioProcessor.onaudioprocess = null;
            audioProcessor.disconnect();
            audioProcessor = null;
        }
        if (audioSource) {
            audioSource.disconnect();
            audioSource = null;
        }
        if (recordingStream) {
            recordingStream.getTracks().forEach(function (track) { track.stop(); });
            recordingStream = null;
        }
        if (audioContext) {
            audioContext.close();
            audioContext = null;
        }
        $("#MicBtn").attr("aria-pressed", "false");
        $("#SiriWave").attr("hidden", true);
        document.body.classList.remove("liza-listening");
        var blob = submitPending ? createWavBlob(audioFrames, recordingSampleRate) : null;
        resetUtterance();
        if (!blob || isSpeaking) return;

        setStatus("Oxirgi buyruqni yakunlayapman...");
        isProcessingVoice = true;
        sendVoiceToDjango(blob, "audio/wav")
            .catch(function (error) { setStatus(error.message || "Ovoz serverda qayta ishlanmadi."); })
            .finally(function () { isProcessingVoice = false; });
    }

    async function sendToDjango(message) {
        var headers = authHeaders();
        headers["Content-Type"] = "application/json";
        var response = await fetch(commandUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: headers,
            body: JSON.stringify({ message: message, internet_search: isInternetSearchEnabled() })
        });
        var data = await response.json().catch(function () { return {}; });
        if (!response.ok) {
            throw new Error(data.error || "Yordamchi serveriga ulanib bo'lmadi.");
        }
            showReply(data);
    }

    async function sendVoiceToDjango(blob, mimeType) {
        var headers = authHeaders();
        var formData = new FormData();
        var extension = mimeType.indexOf("wav") >= 0 ? "wav" : mimeType.indexOf("mp4") >= 0 ? "mp4" : mimeType.indexOf("ogg") >= 0 ? "ogg" : "webm";
        formData.append("audio", blob, "liza-audio." + extension);
        formData.append("internet_search", String(isInternetSearchEnabled()));
        var response = await fetch(apiBaseUrl + "voice/", {
            method: "POST",
            credentials: "same-origin",
            headers: headers,
            body: formData
        });
        var data = await response.json().catch(function () { return {}; });
        if (!response.ok) throw new Error(data.error || "Ovoz serverda qayta ishlanmadi.");
        showReply(data);
    }

    async function sendCommand(message) {
        message = String(message || "").trim();
        if (!message) return;

        var desktopBridge = window.eel && typeof window.eel.allCommands === "function";
        if (!desktopBridge) appendMessage(message, "sender");
        showAssistant();
        setStatus("Buyruq bajarilmoqda...");
        $("#SendBtn, #MicBtn").prop("disabled", true);
        try {
            if (desktopBridge) {
                await window.eel.allCommands(message)();
            } else {
                await sendToDjango(message);
            }
        } catch (error) {
            setStatus(error.message || "Ulanishda xatolik yuz berdi.");
        } finally {
            $("#chatbox").val("");
            $("#SendBtn, #MicBtn").prop("disabled", false);
            updateInputButtons("");
        }
    }

    function startListening() {
        if (window.eel && typeof window.eel.allCommands === "function") {
            showAssistant();
            if (window.eel.playAssistantSound) window.eel.playAssistantSound()();
            window.eel.allCommands()();
            return;
        }
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !(window.AudioContext || window.webkitAudioContext)) {
            setStatus("Bu brauzerda xavfsiz ovoz yozish qo'llanmaydi. Matn kiriting.");
            return;
        }
        if (isListening) {
            stopRecording(true);
            return;
        }

        isListening = true;
        showAssistant();
        setStatus("Tinglayapman. Davom eting yoki mikrofonni bosing.");
        $("#MicBtn").attr("aria-pressed", "true");
        navigator.mediaDevices.getUserMedia({
            audio: {
                channelCount: { ideal: 1 },
                echoCancellation: { ideal: true },
                noiseSuppression: { ideal: true },
                autoGainControl: { ideal: true },
            },
        }).then(async function (stream) {
            if (!isListening) {
                stream.getTracks().forEach(function (track) { track.stop(); });
                return;
            }
            recordingStream = stream;
            var Context = window.AudioContext || window.webkitAudioContext;
            audioContext = new Context({ sampleRate: 16000 });
            await audioContext.resume();
            recordingSampleRate = audioContext.sampleRate;
            audioSource = audioContext.createMediaStreamSource(stream);
            audioProcessor = audioContext.createScriptProcessor(4096, 1, 1);
            audioProcessor.onaudioprocess = function (event) {
                if (!isListening || isSpeaking || isProcessingVoice) return;
                var frame = new Float32Array(event.inputBuffer.getChannelData(0));
                var energy = 0;
                for (var index = 0; index < frame.length; index += 1) energy += frame[index] * frame[index];
                var hasVoice = Math.sqrt(energy / frame.length) > 0.006;
                var now = Date.now();
                if (hasVoice) {
                    lastVoiceAt = now;
                    voicedSamples += frame.length;
                }
                if (lastVoiceAt) {
                    audioFrames.push(frame);
                    utteranceSamples += frame.length;
                    if (now - lastVoiceAt > 900 || utteranceSamples >= recordingSampleRate * 12) {
                        submitCurrentUtterance();
                    }
                }
            };
            var silentOutput = audioContext.createGain();
            silentOutput.gain.value = 0;
            audioSource.connect(audioProcessor);
            audioProcessor.connect(silentOutput);
            silentOutput.connect(audioContext.destination);
            if (!youtubePlayer) {
                speakMadina("Salom, men Lizaman. Sizga qanday yordam beray?", function () {
                    if (isListening) setStatus("Tinglayapman. Davom eting yoki mikrofonni bosing.");
                });
            }
        }).catch(function () {
            isListening = false;
            restoreYoutubeVolume();
            if (audioProcessor) {
                audioProcessor.onaudioprocess = null;
                audioProcessor.disconnect();
                audioProcessor = null;
            }
            if (audioSource) {
                audioSource.disconnect();
                audioSource = null;
            }
            if (recordingStream) {
                recordingStream.getTracks().forEach(function (track) { track.stop(); });
                recordingStream = null;
            }
            if (audioContext) {
                audioContext.close();
                audioContext = null;
            }
            audioFrames = [];
            $("#MicBtn").attr("aria-pressed", "false");
            $("#SiriWave").attr("hidden", true);
            document.body.classList.remove("liza-listening");
            setStatus("Mikrofonga ruxsat berilmadi yoki HTTPS ulanishi yo'q.");
        });
    }

    function updateInputButtons(message) {
        var hasText = String(message || "").trim().length > 0;
        $("#MicBtn").attr("hidden", hasText);
        $("#SendBtn").attr("hidden", !hasText);
    }

    $("#MicBtn").on("click", startListening);
    if (internetSearchToggle) {
        updateInternetSearchToggle();
        internetSearchToggle.addEventListener("click", function () {
            localStorage.setItem(internetSearchStorageKey, String(!isInternetSearchEnabled()));
            updateInternetSearchToggle();
            setStatus(isInternetSearchEnabled()
                ? "Internet-qidiruv yoqildi. Savollaringiz DuckDuckGo’ga yuboriladi; shaxsiy ma’lumotlarni kiritmang."
                : "Internet-qidiruv o‘chirildi. Liza odatdagi rejimda javob beradi.");
        });
    }
    $("#SendBtn").on("click", function () {
        sendCommand($("#chatbox").val());
    });
    $("#chatbox").on("input", function () {
        updateInputButtons($(this).val());
    }).on("keydown", function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            sendCommand($(this).val());
        }
    });

    $("#InstallBtn").on("click", async function () {
        if (!installPrompt) return;
        installPrompt.prompt();
        await installPrompt.userChoice;
        installPrompt = null;
        $(this).attr("hidden", true);
    });

    window.addEventListener("beforeinstallprompt", function (event) {
        event.preventDefault();
        installPrompt = event;
        $("#InstallBtn").attr("hidden", false);
    });

    document.addEventListener("keyup", function (event) {
        if (event.key.toLowerCase() === "j" && (event.metaKey || event.ctrlKey)) {
            startListening();
        }
    });

    if ("serviceWorker" in navigator && window.location.protocol !== "file:") {
        window.addEventListener("load", function () {
            navigator.serviceWorker.register("service-worker.js").catch(function () {});
        });
    }
});
