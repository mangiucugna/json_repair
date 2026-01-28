let timeoutId;
let controller;
const inputEl = document.getElementById('input-json');
const outputEl = document.getElementById('output-json');
const logEl = document.getElementById('log-output');

// Function to update the URL with the input JSON
function updateURL(inputJSON) {
    const url = new URL(window.location);
    url.searchParams.set('json', encodeURIComponent(inputJSON));
    window.history.replaceState({}, '', url);
}

// Function to get JSON from the URL
function getJSONFromURL() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('json') ? decodeURIComponent(urlParams.get('json')) : '';
}

document.addEventListener('DOMContentLoaded', () => {
    const initialJSON = getJSONFromURL();
    if (initialJSON) {
        inputEl.value = initialJSON;
        processInput(initialJSON);
    }
});

inputEl.addEventListener('input', function () {
    const inputJSON = inputEl.value;
    updateURL(inputJSON);
    processInput(inputJSON);
});

function processInput(inputJSON) {
    if (inputJSON.trim() === '') {
        outputEl.value = '';
        logEl.value = '';
        return;
    }

    if (timeoutId) {
        clearTimeout(timeoutId);
    }

    if (controller) {
        controller.abort();
    }

    timeoutId = setTimeout(() => {
        controller = new AbortController();
        fetch('https://mangiucugna.pythonanywhere.com/api/repair-json', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ malformedJSON: inputJSON }),
            signal: controller.signal
        })
        .then(response => response.json())
        .then(data => {
            let formattedJSON, logs;
            if (Array.isArray(data)) {
                [formattedJSON, logs] = data;
            } else {
                formattedJSON = data;
                logs = [{context: "", text: "Nothing to do, this was a valid JSON"}];
            }
            outputEl.value = JSON.stringify(formattedJSON, null, 4);
            const formattedLogs = logs.map(log => {
                return `Context: ${log.context}\nMessage: ${log.text}`;
            }).join('\n\n');
            logEl.value = formattedLogs;
        })
        .catch(error => {
            if (error.name !== 'AbortError') {
                outputEl.value = 'Error formatting JSON: ' + error.message;
                logEl.value = '';
            }
        });
    }, 500);
}
