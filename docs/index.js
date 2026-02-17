let timeoutId;
let controller;
const DEBOUNCE_MS = 500;
const API_URL = "https://mangiucugna.pythonanywhere.com/api/repair-json";
const DEFAULT_SCHEMA_MODE = 'standard';
const SALVAGE_SCHEMA_MODE = 'salvage';
const SCHEMA_REPAIR_MODES = new Set([DEFAULT_SCHEMA_MODE, SALVAGE_SCHEMA_MODE]);
const inputEl = document.getElementById('input-json');
const schemaEl = document.getElementById('schema-json');
const modeEl = document.getElementById('schema-repair-mode');
const outputEl = document.getElementById('output-json');
const logEl = document.getElementById('log-output');
const isChinese = (document.documentElement.lang || '').toLowerCase().startsWith('zh');

const messages = isChinese
    ? {
        noRepairNeeded: "无需修复，输入已经是有效 JSON。",
        schemaParseError: "Schema 必须是有效的 JSON 文本。",
        schemaTypeError: "Schema 顶层只能是 JSON 对象或布尔值（true/false）。",
        schemaHint: "请修正 Schema 后重试；当前未向 API 发送请求。",
        schemaClientErrorPrefix: "Schema 输入错误：",
        schemaModeError: "Schema 修复模式只能是 standard 或 salvage。",
        schemaModeNeedsSchema: "salvage 模式必须提供 Schema。",
        formatErrorPrefix: "JSON 修复失败：",
        unexpectedResponse: "服务器返回了无法解析的响应。",
        httpErrorPrefix: "请求失败，状态码：",
        contextLabel: "上下文",
        messageLabel: "信息",
    }
    : {
        noRepairNeeded: "Nothing to do, this was already valid JSON.",
        schemaParseError: "Schema must be valid JSON.",
        schemaTypeError: "Schema must be a top-level JSON object or boolean (true/false).",
        schemaHint: "Fix the schema and try again; no API request was sent.",
        schemaClientErrorPrefix: "Schema input error: ",
        schemaModeError: "Schema repair mode must be standard or salvage.",
        schemaModeNeedsSchema: "salvage mode requires a schema.",
        formatErrorPrefix: "Error formatting JSON: ",
        unexpectedResponse: "The server returned an unreadable response.",
        httpErrorPrefix: "Request failed with status ",
        contextLabel: "Context",
        messageLabel: "Message",
    };

function updateURL(inputJSON, schemaJSON, schemaMode) {
    const url = new URL(window.location);
    url.searchParams.set('json', encodeURIComponent(inputJSON));
    if (schemaJSON.trim() === '') {
        url.searchParams.delete('schema');
    } else {
        url.searchParams.set('schema', encodeURIComponent(schemaJSON));
    }
    if (schemaMode === DEFAULT_SCHEMA_MODE) {
        url.searchParams.delete('schema_mode');
    } else {
        url.searchParams.set('schema_mode', schemaMode);
    }
    window.history.replaceState({}, '', url);
}

function getValueFromURL(param) {
    const urlParams = new URLSearchParams(window.location.search);
    const rawValue = urlParams.get(param);
    return rawValue ? decodeURIComponent(rawValue) : '';
}

function showClientError(message, details = '') {
    outputEl.value = message;
    logEl.value = details;
}

function formatLogs(logs) {
    if (!Array.isArray(logs) || logs.length === 0) {
        return messages.noRepairNeeded;
    }
    return logs
        .map((log) => `${messages.contextLabel}: ${log.context}\n${messages.messageLabel}: ${log.text}`)
        .join('\n\n');
}

function parseSchema(schemaText) {
    const trimmedSchema = schemaText.trim();
    if (trimmedSchema === '') {
        return { schema: undefined, error: null };
    }

    let parsedSchema;
    try {
        parsedSchema = JSON.parse(trimmedSchema);
    } catch {
        return { schema: undefined, error: messages.schemaParseError };
    }

    const topLevelType = typeof parsedSchema;
    const isValidTopLevel = (topLevelType === 'object' && parsedSchema !== null && !Array.isArray(parsedSchema))
        || topLevelType === 'boolean';
    if (!isValidTopLevel) {
        return { schema: undefined, error: messages.schemaTypeError };
    }

    return { schema: parsedSchema, error: null };
}

function parseSchemaRepairMode(modeText) {
    const trimmedMode = modeText.trim();
    if (trimmedMode === '') {
        return { schemaMode: DEFAULT_SCHEMA_MODE, error: null };
    }
    if (!SCHEMA_REPAIR_MODES.has(trimmedMode)) {
        return { schemaMode: DEFAULT_SCHEMA_MODE, error: messages.schemaModeError };
    }
    return { schemaMode: trimmedMode, error: null };
}

function handleInputChange() {
    const inputJSON = inputEl.value;
    const schemaJSON = schemaEl ? schemaEl.value : '';
    const schemaMode = modeEl ? modeEl.value : DEFAULT_SCHEMA_MODE;
    updateURL(inputJSON, schemaJSON, schemaMode);
    processInput(inputJSON, schemaJSON, schemaMode);
}

document.addEventListener('DOMContentLoaded', () => {
    const initialJSON = getValueFromURL('json');
    const initialSchema = getValueFromURL('schema');
    const initialSchemaMode = getValueFromURL('schema_mode');
    if (initialJSON) {
        inputEl.value = initialJSON;
    }
    if (schemaEl && initialSchema) {
        schemaEl.value = initialSchema;
    }
    if (modeEl && SCHEMA_REPAIR_MODES.has(initialSchemaMode)) {
        modeEl.value = initialSchemaMode;
    }
    if (initialJSON) {
        processInput(initialJSON, initialSchema, modeEl ? modeEl.value : DEFAULT_SCHEMA_MODE);
    }
});

inputEl.addEventListener('input', handleInputChange);
if (schemaEl) {
    schemaEl.addEventListener('input', handleInputChange);
}
if (modeEl) {
    modeEl.addEventListener('change', handleInputChange);
}

function processInput(inputJSON, schemaJSON = '', schemaMode = DEFAULT_SCHEMA_MODE) {
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

    const { schema, error } = parseSchema(schemaJSON);
    if (error) {
        showClientError(
            `${messages.schemaClientErrorPrefix}${error}`,
            messages.schemaHint
        );
        return;
    }
    const { schemaMode: parsedSchemaMode, error: schemaModeError } = parseSchemaRepairMode(schemaMode);
    if (schemaModeError) {
        showClientError(
            `${messages.schemaClientErrorPrefix}${schemaModeError}`,
            messages.schemaHint
        );
        return;
    }
    if (parsedSchemaMode === SALVAGE_SCHEMA_MODE && schema === undefined) {
        showClientError(
            `${messages.schemaClientErrorPrefix}${messages.schemaModeNeedsSchema}`,
            messages.schemaHint
        );
        return;
    }

    timeoutId = setTimeout(() => {
        controller = new AbortController();
        const requestBody = { malformedJSON: inputJSON };
        if (schema !== undefined) {
            requestBody.schema = schema;
        }
        requestBody.schemaRepairMode = parsedSchemaMode;

        fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody),
            signal: controller.signal
        })
        .then(async (response) => {
            let data;
            try {
                data = await response.json();
            } catch {
                throw new Error(messages.unexpectedResponse);
            }

            if (!response.ok) {
                if (data && typeof data.error === 'string') {
                    throw new Error(data.error);
                }
                throw new Error(`${messages.httpErrorPrefix}${response.status}`);
            }

            if (data && typeof data === 'object' && !Array.isArray(data) && typeof data.error === 'string') {
                throw new Error(data.error);
            }

            return data;
        })
        .then((data) => {
            let formattedJSON = data;
            let logs = [];
            if (Array.isArray(data)) {
                [formattedJSON, logs] = data;
            }

            outputEl.value = JSON.stringify(formattedJSON, null, 4);
            logEl.value = formatLogs(logs);
        })
        .catch((error) => {
            if (error.name !== 'AbortError') {
                showClientError(`${messages.formatErrorPrefix}${error.message}`);
            }
        });
    }, DEBOUNCE_MS);
}
