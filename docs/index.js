let timeoutId;
let controller;

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
        document.getElementById('input-json').value = initialJSON;
        processInput(initialJSON);
    }
});

document.getElementById('input-json').addEventListener('input', function () {
    const inputJSON = document.getElementById('input-json').value;
    updateURL(inputJSON);
    processInput(inputJSON);
});

function processInput(inputJSON) {
    if (inputJSON.trim() === '') {
        document.getElementById('output-json').value = '';
        document.getElementById('log-output').value = '';
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
            const [formattedJSON, logs] = data;
            document.getElementById('output-json').value = JSON.stringify(formattedJSON, null, 4);
            const formattedLogs = logs.map(log => {
                return `Context: ${log.context}\nMessage: ${log.text}`;
            }).join('\n\n');
            document.getElementById('log-output').value = formattedLogs;
        })
        .catch(error => {
            if (error.name !== 'AbortError') {
                document.getElementById('output-json').value = 'Error formatting JSON: ' + error.message;
                document.getElementById('log-output').value = '';
            }
        });
    }, 500);
}
