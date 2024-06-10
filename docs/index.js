let timeoutId;
let controller;

document.getElementById('input-json').addEventListener('input', function () {
    const inputJSON = document.getElementById('input-json').value;

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
});
