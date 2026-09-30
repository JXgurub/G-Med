$(document).ready(function () {
    var installPrompt = null;
    var isListening = false;
    var recordingStream = null;
    var audioContext = null;
    var audioSource = null;
    var audioProcessor = null;
    var recordingSampleRate = 16000;
    var recordingTimer = null;
    var audioFrames = [];
    var apiUrlMeta = document.querySelector('meta[name="liza-api-url"]');
    var commandUrl = apiUrlMeta ? apiUrlMeta.content : "/api/liza/command/";
    var apiBaseUrl = commandUrl.replace(/command\/?$/, "");

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
        $("#Oval").attr("hidden", true);
        $("#SiriWave").attr("hidden", false);
    }

    function setStatus(message) {
        $(".siri-message").text(message);
    }

    function appendMessage(message, role) {
        var chatBox = document.getElementById("chat-canvas-body");
        if (!chatBox || !message) return;

        var row = document.createElement("div");
        var width = document.createElement("div");
        var bubble = document.createElement("div");
        row.className = "row justify-content-" + (role === "sender" ? "end" : "start") + " mb-3";
        width.className = "width-size";
        bubble.className = role + "_message";
        bubble.textContent = message;
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
        var audioUrl = URL.createObjectURL(new Blob([bytes], { type: data.content_type || "audio/mpeg" }));
        var player = new Audio(audioUrl);
        player.onended = function () {
            URL.revokeObjectURL(audioUrl);
            if (onEnded) onEnded();
        };
        player.onerror = function () { URL.revokeObjectURL(audioUrl); };
        try {
            await player.play();
        } catch (error) {
            URL.revokeObjectURL(audioUrl);
            throw error;
        }
    }

    function showReply(data) {
        if (data.transcript) appendMessage(data.transcript, "sender");
        if (data.reply) {
            appendMessage(data.reply, "receiver");
            setStatus(data.reply);
            var openPatientProfile = data.action === "open_profile";
            speakMadina(data.reply, openPatientProfile ? function () {
                window.location.assign("/patient?tab=profile");
            } : null).catch(function () {
                setStatus("Madina ovozi hozir ijro etilmadi. Javob matni ko'rsatildi.");
                if (openPatientProfile) window.location.assign("/patient?tab=profile");
            });
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

    function stopRecording() {
        if (!isListening) return;
        isListening = false;
        window.clearTimeout(recordingTimer);
        recordingTimer = null;
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
        var blob = createWavBlob(audioFrames, recordingSampleRate);
        audioFrames = [];
        if (!blob) {
            setStatus("Ovoz yozuvi bo'sh.");
            return;
        }
        setStatus("Ovoz G-MED serverida mahalliy qayta ishlanmoqda...");
        $("#MicBtn").prop("disabled", true);
        sendVoiceToDjango(blob, "audio/wav")
            .catch(function (error) { setStatus(error.message); })
            .finally(function () { $("#MicBtn").prop("disabled", false); });
    }

    async function sendToDjango(message) {
        var headers = authHeaders();
        headers["Content-Type"] = "application/json";
        var response = await fetch(commandUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: headers,
            body: JSON.stringify({ message: message })
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
            stopRecording();
            return;
        }

        isListening = true;
        showAssistant();
        setStatus("Tinglayapman. Yozuvni tugatish uchun mikrofonni bosing.");
        $("#MicBtn").attr("aria-pressed", "true");
        navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 } }).then(async function (stream) {
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
                audioFrames.push(new Float32Array(event.inputBuffer.getChannelData(0)));
            };
            var silentOutput = audioContext.createGain();
            silentOutput.gain.value = 0;
            audioSource.connect(audioProcessor);
            audioProcessor.connect(silentOutput);
            silentOutput.connect(audioContext.destination);
            recordingTimer = window.setTimeout(function () {
                stopRecording();
            }, 20000);
        }).catch(function () {
            isListening = false;
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
            setStatus("Mikrofonga ruxsat berilmadi yoki HTTPS ulanishi yo'q.");
        });
    }

    function updateInputButtons(message) {
        var hasText = String(message || "").trim().length > 0;
        $("#MicBtn").attr("hidden", hasText);
        $("#SendBtn").attr("hidden", !hasText);
    }

    $("#MicBtn").on("click", startListening);
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
