let timeoutId;
let controller;
const DEBOUNCE_MS = 500;
const API_URL = "https://mangiucugna.pythonanywhere.com/api/repair-json";
const DEFAULT_SCHEMA_MODE = 'standard';
const SALVAGE_SCHEMA_MODE = 'salvage';
const SCHEMA_REPAIR_MODES = new Set([DEFAULT_SCHEMA_MODE, SALVAGE_SCHEMA_MODE]);
const URL_STATE_HASH_KEY = 'jr';
const URL_STATE_VERSION = 'v1';
const RAW_URL_STATE_CODEC = 'u';
const DRAFT_STORAGE_KEY = 'jsonRepairDraft.v1';
const URL_STATE_CODECS = [
    { id: 'd', format: 'deflate' },
    { id: 'g', format: 'gzip' },
];
const inputEl = document.getElementById('input-json');
const schemaEl = document.getElementById('schema-json');
const modeEl = document.getElementById('schema-repair-mode');
const outputEl = document.getElementById('output-json');
const logEl = document.getElementById('log-output');
const successSupportEl = document.getElementById('success-support');
const copyRepoLinkBtn = document.getElementById('copy-repo-link');
const supportCopyStatusEl = document.getElementById('support-copy-status');
const copyShareLinkBtn = document.getElementById('copy-share-link');
const shareCopyStatusEl = document.getElementById('share-copy-status');
const isChinese = (document.documentElement.lang || '').toLowerCase().startsWith('zh');
const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();
const supportedURLStateCodec = getSupportedURLStateCodec();
const REPO_URL = "https://github.com/mangiucugna/json_repair/";
let urlUpdateSequence = 0;

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
        supportCopySuccess: "仓库链接已复制，欢迎发给同事或朋友。",
        supportCopyUnavailable: "当前浏览器不支持自动复制，请手动复制仓库链接。",
        supportCopyFailure: "复制失败，请手动复制仓库链接。",
        shareCopySuccess: "分享链接已复制，可直接发给同事或贴到 Issue 里。",
        shareCopyUnavailable: "当前浏览器不支持自动复制分享链接。",
        shareCopyFailure: "生成或复制分享链接失败，请重试。",
        shareCopyEmpty: "先输入 JSON 或 Schema，再复制分享链接。",
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
        supportCopySuccess: "Repository link copied. Share it with someone who needs it.",
        supportCopyUnavailable: "Clipboard access is unavailable. Copy the repository link manually.",
        supportCopyFailure: "Could not copy the repository link. Copy it manually instead.",
        shareCopySuccess: "Share link copied. Send it to someone who needs the exact same example.",
        shareCopyUnavailable: "Clipboard access is unavailable for share links in this browser.",
        shareCopyFailure: "Could not create or copy the share link. Try again.",
        shareCopyEmpty: "Enter JSON or a schema before copying a share link.",
    };

function setSupportVisibility(isVisible) {
    if (!successSupportEl) {
        return;
    }
    successSupportEl.classList.toggle('hidden', !isVisible);
}

function setSupportCopyStatus(message = '') {
    if (supportCopyStatusEl) {
        supportCopyStatusEl.textContent = message;
    }
}

function setShareCopyStatus(message = '') {
    if (shareCopyStatusEl) {
        shareCopyStatusEl.textContent = message;
    }
}

async function writeTextToClipboard(text) {
    if (!navigator.clipboard || typeof navigator.clipboard.writeText !== 'function') {
        return 'unavailable';
    }

    try {
        await navigator.clipboard.writeText(text);
        return 'success';
    } catch {
        return 'failure';
    }
}

async function copyRepositoryLink() {
    const result = await writeTextToClipboard(REPO_URL);
    if (result === 'success') {
        setSupportCopyStatus(messages.supportCopySuccess);
        return;
    }

    setSupportCopyStatus(
        result === 'unavailable'
            ? messages.supportCopyUnavailable
            : messages.supportCopyFailure
    );
}

function getSupportedURLStateCodec() {
    if (typeof CompressionStream !== 'function' || typeof DecompressionStream !== 'function') {
        return null;
    }

    for (const codec of URL_STATE_CODECS) {
        try {
            new CompressionStream(codec.format);
            new DecompressionStream(codec.format);
            return codec;
        } catch {
            continue;
        }
    }

    return null;
}

function encodeBase64URL(bytes) {
    let binary = '';
    const chunkSize = 0x8000;
    for (let index = 0; index < bytes.length; index += chunkSize) {
        const chunk = bytes.subarray(index, index + chunkSize);
        binary += String.fromCharCode(...chunk);
    }
    return btoa(binary)
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=+$/u, '');
}

function decodeBase64URL(value) {
    const padding = (4 - (value.length % 4)) % 4;
    const paddedValue = `${value}${'='.repeat(padding)}`
        .replace(/-/g, '+')
        .replace(/_/g, '/');
    const binary = atob(paddedValue);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
}

async function transformBytes(bytes, streamFactory) {
    const stream = new Blob([bytes]).stream().pipeThrough(streamFactory());
    const buffer = await new Response(stream).arrayBuffer();
    return new Uint8Array(buffer);
}

async function compressURLState(rawBytes) {
    if (!supportedURLStateCodec) {
        return { codec: RAW_URL_STATE_CODEC, bytes: rawBytes };
    }

    const compressedBytes = await transformBytes(
        rawBytes,
        () => new CompressionStream(supportedURLStateCodec.format)
    );
    if (compressedBytes.length >= rawBytes.length) {
        return { codec: RAW_URL_STATE_CODEC, bytes: rawBytes };
    }

    return { codec: supportedURLStateCodec.id, bytes: compressedBytes };
}

function buildCleanURL() {
    const url = new URL(window.location.href);
    url.search = '';
    url.hash = '';
    return url;
}

function getCurrentState() {
    return {
        inputJSON: inputEl.value,
        schemaJSON: schemaEl ? schemaEl.value : '',
        schemaMode: modeEl ? modeEl.value : DEFAULT_SCHEMA_MODE,
    };
}

function buildURLState(inputJSON, schemaJSON, schemaMode) {
    const state = {};

    if (inputJSON !== '') {
        state.j = inputJSON;
    }
    if (schemaJSON.trim() !== '') {
        state.s = schemaJSON;
    }
    if (schemaMode !== DEFAULT_SCHEMA_MODE) {
        state.m = schemaMode;
    }

    return state;
}

function hasURLState(state) {
    return Object.keys(state).length > 0;
}

function hasStateContent(state) {
    return !!state && (
        state.inputJSON !== ''
        || state.schemaJSON.trim() !== ''
        || state.schemaMode !== DEFAULT_SCHEMA_MODE
    );
}

async function encodeURLState(state) {
    const rawBytes = textEncoder.encode(JSON.stringify(state));
    const { codec, bytes } = await compressURLState(rawBytes);
    return `${URL_STATE_VERSION}.${codec}.${encodeBase64URL(bytes)}`;
}

function parseURLState(state) {
    if (!state || typeof state !== 'object' || Array.isArray(state)) {
        return null;
    }

    return {
        inputJSON: typeof state.j === 'string' ? state.j : '',
        schemaJSON: typeof state.s === 'string' ? state.s : '',
        schemaMode: typeof state.m === 'string' && SCHEMA_REPAIR_MODES.has(state.m)
            ? state.m
            : DEFAULT_SCHEMA_MODE,
    };
}

async function decodeURLState(payload) {
    try {
        const parts = payload.split('.');
        if (parts.length !== 3) {
            return null;
        }

        const [version, codecId, encodedValue] = parts;
        if (version !== URL_STATE_VERSION || encodedValue === '') {
            return null;
        }

        let bytes = decodeBase64URL(encodedValue);
        if (codecId !== RAW_URL_STATE_CODEC) {
            const codec = URL_STATE_CODECS.find((candidate) => candidate.id === codecId);
            if (!codec || typeof DecompressionStream !== 'function') {
                return null;
            }
            bytes = await transformBytes(bytes, () => new DecompressionStream(codec.format));
        }

        return parseURLState(JSON.parse(textDecoder.decode(bytes)));
    } catch {
        return null;
    }
}

function getLegacyValueFromURL(param) {
    const urlParams = new URLSearchParams(window.location.search);
    const rawValue = urlParams.get(param);
    return rawValue ? decodeURIComponent(rawValue) : '';
}

function getLegacyStateFromURL() {
    return parseURLState({
        j: getLegacyValueFromURL('json'),
        s: getLegacyValueFromURL('schema'),
        m: getLegacyValueFromURL('schema_mode'),
    });
}

async function getStateFromURL() {
    const hashPrefix = `#${URL_STATE_HASH_KEY}=`;
    if (window.location.hash.startsWith(hashPrefix)) {
        const hashState = await decodeURLState(window.location.hash.slice(hashPrefix.length));
        if (hasStateContent(hashState)) {
            return hashState;
        }
    }

    const legacyState = getLegacyStateFromURL();
    return hasStateContent(legacyState) ? legacyState : null;
}

function getDraftState() {
    try {
        const serializedState = window.localStorage.getItem(DRAFT_STORAGE_KEY);
        if (!serializedState) {
            return null;
        }
        const draftState = parseURLState(JSON.parse(serializedState));
        return hasStateContent(draftState) ? draftState : null;
    } catch {
        return null;
    }
}

function persistDraftState(inputJSON, schemaJSON, schemaMode) {
    try {
        const nextState = buildURLState(inputJSON, schemaJSON, schemaMode);
        if (!hasURLState(nextState)) {
            window.localStorage.removeItem(DRAFT_STORAGE_KEY);
            return;
        }
        window.localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(nextState));
    } catch {
        return;
    }
}

async function buildShareURL(inputJSON, schemaJSON, schemaMode) {
    const state = buildURLState(inputJSON, schemaJSON, schemaMode);
    if (!hasURLState(state)) {
        return null;
    }

    const url = buildCleanURL();
    const encodedState = await encodeURLState(state);
    // Store shared state in the fragment so large payloads do not hit static-host query limits.
    url.hash = `${URL_STATE_HASH_KEY}=${encodedState}`;
    return url.toString();
}

async function updateURL(inputJSON, schemaJSON, schemaMode) {
    const requestId = ++urlUpdateSequence;
    const nextState = buildURLState(inputJSON, schemaJSON, schemaMode);
    const url = buildCleanURL();

    if (hasURLState(nextState)) {
        try {
            const encodedState = await encodeURLState(nextState);
            if (requestId !== urlUpdateSequence) {
                return;
            }
            url.hash = `${URL_STATE_HASH_KEY}=${encodedState}`;
        } catch {
            return;
        }
    }

    if (requestId !== urlUpdateSequence) {
        return;
    }

    window.history.replaceState({}, '', url);
}

async function copyShareLink() {
    const { inputJSON, schemaJSON, schemaMode } = getCurrentState();
    const state = buildURLState(inputJSON, schemaJSON, schemaMode);
    if (!hasURLState(state)) {
        setShareCopyStatus(messages.shareCopyEmpty);
        return;
    }

    let shareURL;
    try {
        shareURL = await buildShareURL(inputJSON, schemaJSON, schemaMode);
    } catch {
        setShareCopyStatus(messages.shareCopyFailure);
        return;
    }

    const result = await writeTextToClipboard(shareURL);
    if (result === 'success') {
        setShareCopyStatus(messages.shareCopySuccess);
        return;
    }

    setShareCopyStatus(
        result === 'unavailable'
            ? messages.shareCopyUnavailable
            : messages.shareCopyFailure
    );
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
    const { inputJSON, schemaJSON, schemaMode } = getCurrentState();
    persistDraftState(inputJSON, schemaJSON, schemaMode);
    setShareCopyStatus('');
    void updateURL(inputJSON, schemaJSON, schemaMode);
    processInput(inputJSON, schemaJSON, schemaMode);
}

document.addEventListener('DOMContentLoaded', async () => {
    const urlState = await getStateFromURL();
    const draftState = urlState ? null : getDraftState();
    const initialState = urlState || draftState;
    const initialJSON = initialState ? initialState.inputJSON : '';
    const initialSchema = initialState ? initialState.schemaJSON : '';
    const initialSchemaMode = initialState ? initialState.schemaMode : DEFAULT_SCHEMA_MODE;
    const resolvedSchemaMode = SCHEMA_REPAIR_MODES.has(initialSchemaMode)
        ? initialSchemaMode
        : DEFAULT_SCHEMA_MODE;

    if (initialJSON !== '') {
        inputEl.value = initialJSON;
    }
    if (schemaEl && initialSchema !== '') {
        schemaEl.value = initialSchema;
    }
    if (modeEl) {
        modeEl.value = resolvedSchemaMode;
    }

    if (initialState) {
        persistDraftState(initialJSON, initialSchema, resolvedSchemaMode);
        void updateURL(initialJSON, initialSchema, resolvedSchemaMode);
    }

    if (initialJSON) {
        processInput(initialJSON, initialSchema, resolvedSchemaMode);
    }
});

inputEl.addEventListener('input', handleInputChange);
if (schemaEl) {
    schemaEl.addEventListener('input', handleInputChange);
}
if (modeEl) {
    modeEl.addEventListener('change', handleInputChange);
}
if (copyRepoLinkBtn) {
    copyRepoLinkBtn.addEventListener('click', () => {
        void copyRepositoryLink();
    });
}
if (copyShareLinkBtn) {
    copyShareLinkBtn.addEventListener('click', () => {
        void copyShareLink();
    });
}

function processInput(inputJSON, schemaJSON = '', schemaMode = DEFAULT_SCHEMA_MODE) {
    if (inputJSON.trim() === '') {
        outputEl.value = '';
        logEl.value = '';
        setSupportVisibility(false);
        setSupportCopyStatus('');
        return;
    }

    if (timeoutId) {
        clearTimeout(timeoutId);
    }

    if (controller) {
        controller.abort();
    }

    setSupportVisibility(false);
    setSupportCopyStatus('');

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
            setSupportVisibility(true);
            setSupportCopyStatus('');
        })
        .catch((error) => {
            if (error.name !== 'AbortError') {
                setSupportVisibility(false);
                showClientError(`${messages.formatErrorPrefix}${error.message}`);
            }
        });
    }, DEBOUNCE_MS);
}
