$(document).ready(function () {
    if (!window.eel || typeof window.eel.expose !== "function") return;



    // Display Speak Message
    eel.expose(DisplayMessage)
    function DisplayMessage(message) {
        $(".siri-message").text(String(message || ""));
    }

    function appendChatMessage(message, role) {
        var text = String(message || "");
        if (text.trim() === "") {
            return;
        }

        var chatBox = document.getElementById("chat-canvas-body");
        var row = document.createElement("div");
        var width = document.createElement("div");
        var bubble = document.createElement("div");

        row.className = "row justify-content-" + (role === "sender" ? "end" : "start") + " mb-4";
        width.className = "width-size";
        bubble.className = role + "_message";
        bubble.textContent = text;
        width.appendChild(bubble);
        row.appendChild(width);
        chatBox.appendChild(row);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    // Display hood
    eel.expose(ShowHood)
    function ShowHood() {
        $("#Oval").attr("hidden", false);
        $("#SiriWave").attr("hidden", true);
    }

    eel.expose(senderText)
    function senderText(message) {
        appendChatMessage(message, "sender");
    }

    eel.expose(receiverText)
    function receiverText(message) {
        appendChatMessage(message, "receiver");
    }


});