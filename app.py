import asyncio
import json
import base64
import httpx
from flask import Flask, request, jsonify
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf import json_format
from google.protobuf.internal import builder as _builder

# ── PROTO INLINE (no separate file needed) ───────────────────
_sym_db = _symbol_database.Default()
_DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\x0e\x46reeFire.proto\"c\n\x08LoginReq\x12\x0f\n\x07open_id\x18\x16 \x01(\t'
    b'\x12\x14\n\x0copen_id_type\x18\x17 \x01(\t\x12\x13\n\x0blogin_token\x18\x1d \x01(\t'
    b'\x12\x1b\n\x13orign_platform_type\x18\x63 \x01(\t\"]\n\x10\x42lacklistInfoRes'
    b'\x12\x1e\n\nban_reason\x18\x01 \x01(\x0e\x32\n.BanReason\x12\x17\n\x0f\x65xpire_duration'
    b'\x18\x02 \x01(\r\x12\x10\n\x08\x62\x61n_time\x18\x03 \x01(\r\"f\n\x0eLoginQueueInfo'
    b'\x12\r\n\x05\x61llow\x18\x01 \x01(\x08\x12\x16\n\x0equeue_position\x18\x02 \x01(\r'
    b'\x12\x16\n\x0eneed_wait_secs\x18\x03 \x01(\r\x12\x15\n\rqueue_is_full\x18\x04 \x01(\x08'
    b'\"\xa0\x03\n\x08LoginRes\x12\x12\n\naccount_id\x18\x01 \x01(\x04\x12\x13\n\x0block_region'
    b'\x18\x02 \x01(\t\x12\x13\n\x0bnoti_region\x18\x03 \x01(\t\x12\x11\n\tip_region\x18\x04'
    b' \x01(\t\x12\x19\n\x11\x61gora_environment\x18\x05 \x01(\t\x12\x19\n\x11new_active_region'
    b'\x18\x06 \x01(\t\x12\x19\n\x11recommend_regions\x18\x07 \x03(\t\x12\r\n\x05token\x18\x08'
    b' \x01(\t\x12\x0b\n\x03ttl\x18\t \x01(\r\x12\x12\n\nserver_url\x18\n \x01(\t\x12\x16\n'
    b'\x0e\x65mulator_score\x18\x0b \x01(\r\x12$\n\tblacklist\x18\x0c \x01(\x0b\x32\x11'
    b'.BlacklistInfoRes\x12#\n\nqueue_info\x18\r \x01(\x0b\x32\x0f.LoginQueueInfo\x12\x0e\n'
    b'\x06tp_url\x18\x0e \x01(\t\x12\x15\n\rapp_server_id\x18\x0f \x01(\r\x12\x0f\n\x07'
    b'\x61no_url\x18\x10 \x01(\t\x12\x0f\n\x07ip_city\x18\x11 \x01(\t\x12\x16\n\x0e'
    b'ip_subdivision\x18\x12 \x01(\t*\xa8\x01\n\tBanReason\x12\x16\n\x12\x42\x41N_REASON_UNKNOWN'
    b'\x10\x00\x12\x1b\n\x17\x42\x41N_REASON_IN_GAME_AUTO\x10\x01\x12\x15\n\x11\x42\x41N_REASON'
    b'_REFUND\x10\x02\x12\x15\n\x11\x42\x41N_REASON_OTHERS\x10\x03\x12\x16\n\x12\x42\x41N_REASON'
    b'_SKINMOD\x10\x04\x12 \n\x1b\x42\x41N_REASON_IN_GAME_AUTO_NEW\x10\xf6\x07\x62\x06proto3'
)
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(_DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(_DESCRIPTOR, 'FreeFire_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
    _DESCRIPTOR._options = None

# ── APP CONFIG ───────────────────────────────────────────────
app = Flask(__name__)

# 🚨 SIRF YAHAN LIMIT BADLO 🚨
LIMIT = 1000

REGION          = "IND"
RELEASE_VERSION = "OB52"
USER_AGENT      = "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)"
MAIN_KEY        = base64.b64decode('WWcmdGMlREV1aDYlWmNeOA==')
MAIN_IV         = base64.b64decode('Nm95WkRyMjJFM3ljaGpNJQ==')
TOKENS_FILE     = "/tmp/tokens.json"
UIDPASS_FILE    = "uidpass.json"

# ── CRYPTO ───────────────────────────────────────────────────

def _manual_pad(data):
    pad_len = AES.block_size - (len(data) % AES.block_size)
    return data + bytes([pad_len] * pad_len)

def aes_encrypt_proto(plaintext):
    return AES.new(MAIN_KEY, AES.MODE_CBC, MAIN_IV).encrypt(_manual_pad(plaintext))

def encrypt_api(hex_str):
    return AES.new(MAIN_KEY, AES.MODE_CBC, MAIN_IV).encrypt(pad(bytes.fromhex(hex_str), AES.block_size))

def Encrypt_ID(number):
    try:
        number = int(number)
        encoded_bytes = []
        while True:
            byte = number & 0x7F
            number >>= 7
            if number:
                byte |= 0x80
            encoded_bytes.append(byte)
            if not number:
                break
        return bytes(encoded_bytes).hex()
    except Exception:
        return ""

def get_sender_uid(token):
    try:
        payload = token.split('.')[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        data = json.loads(base64.b64decode(payload).decode('utf-8'))
        uid = data.get("external_uid") or data.get("account_id")
        return int(uid)
    except Exception:
        return 0

def game_headers(token, region):
    return {
        "Host": f"client.{region.lower()}.freefiremobile.com",
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip",
        "Authorization": f"Bearer {token}",
        "X-GA": "v1 1",
        "ReleaseVersion": RELEASE_VERSION,
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.11f1",
        "Connection": "Keep-Alive",
    }

# ── TOKEN GENERATION ─────────────────────────────────────────

async def fetch_access_token(uid, password):
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    payload = (
        f"uid={uid}&password={password}"
        "&response_type=token&client_type=2"
        "&client_secret=2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
        "&client_id=100067"
    )
    headers = {"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, data=payload, headers=headers)
        data = resp.json()
    return data.get("access_token", ""), data.get("open_id", "")

async def fetch_jwt_for_account(acc):
    try:
        access_token, open_id = await fetch_access_token(acc['uid'], acc['password'])
        if not access_token:
            return None
        login_req = LoginReq()
        json_format.ParseDict({
            "open_id": open_id,
            "open_id_type": "4",
            "login_token": access_token,
            "orign_platform_type": "4",
        }, login_req)
        encrypted = aes_encrypt_proto(login_req.SerializeToString())
        headers = {
            "User-Agent": USER_AGENT, "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip", "Content-Type": "application/octet-stream",
            "Expect": "100-continue", "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1", "ReleaseVersion": RELEASE_VERSION,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post("https://loginbp.ggblueshark.com/MajorLogin", data=encrypted, headers=headers)
        login_res = LoginRes()
        login_res.ParseFromString(resp.content)
        msg = json.loads(json_format.MessageToJson(login_res))
        token = msg.get("token", "")
        return {"token": token} if token else None
    except Exception:
        return None

async def generate_tokens():
    try:
        with open(UIDPASS_FILE, "r") as f:
            accs = json.load(f)[:LIMIT]
    except Exception:
        return []
    sem = asyncio.Semaphore(50)
    results = []
    async def process(acc):
        async with sem:
            t = await fetch_jwt_for_account(acc)
            if t:
                results.append(t)
    await asyncio.gather(*(process(acc) for acc in accs))
    with open(TOKENS_FILE, "w") as f:
        json.dump(results, f)
    return results

def load_tokens():
    try:
        with open(TOKENS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

# ── ACTIONS ──────────────────────────────────────────────────

async def do_visit(client, token, target_uid, region):
    url = f"https://client.{region.lower()}.freefiremobile.com/GetPlayerPersonalShow"
    try:
        payload = encrypt_api(f"08{Encrypt_ID(target_uid)}1007")
        r = await client.post(url, headers=game_headers(token, region), content=payload, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

async def do_addfriend(client, token, target_uid, region):
    url = f"https://client.{region.lower()}.freefiremobile.com/RequestAddingFriend"
    try:
        sender_uid = get_sender_uid(token)
        if not sender_uid:
            return False
        payload = encrypt_api(f"08{Encrypt_ID(sender_uid)}10{Encrypt_ID(target_uid)}1801")
        r = await client.post(url, headers=game_headers(token, region), content=payload, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

async def run_bulk(target_uid, action, limit, region):
    tokens = load_tokens()
    if not tokens:
        tokens = await generate_tokens()
    if not tokens:
        return {"error": "Tokens nahi hain. /refresh call karo pehle."}
    sem = asyncio.Semaphore(50)
    async def bounded(td):
        async with sem:
            t = td.get("token", "")
            if action == "visit":
                return await do_visit(client, t, target_uid, region)
            elif action == "add":
                return await do_addfriend(client, t, target_uid, region)
            return False
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(bounded(td) for td in tokens[:limit]))
    return {
        "status": "success", "action": action,
        "target_uid": target_uid, "region": region,
        "accounts_tried": len(results),
        "successful_requests": results.count(True),
    }

# ── ROUTES ───────────────────────────────────────────────────

@app.route('/')
def home():
    return jsonify({"msg": "Visit Bot Running!", "limit": LIMIT, "tokens_cached": len(load_tokens())}), 200

@app.route('/refresh')
async def refresh_endpoint():
    tokens = await generate_tokens()
    return jsonify({"status": "success", "msg": f"{len(tokens)} tokens generate ho gaye"}), 200

@app.route('/visit', methods=['GET'])
async def visit_endpoint():
    uid = request.args.get('uid')
    if not uid:
        return jsonify({"error": "UID zaruri hai"}), 400
    limit = int(request.args.get('limit', LIMIT))
    region = request.args.get('server_name', request.args.get('region', REGION)).replace('(','').replace(')','').strip().upper()
    return jsonify(await run_bulk(uid, "visit", limit, region)), 200

@app.route('/addfriend', methods=['GET'])
async def addfriend_endpoint():
    uid = request.args.get('uid')
    if not uid:
        return jsonify({"error": "UID zaruri hai"}), 400
    limit = int(request.args.get('limit', LIMIT))
    region = request.args.get('server_name', request.args.get('region', REGION)).replace('(','').replace(')','').strip().upper()
    return jsonify(await run_bulk(uid, "add", limit, region)), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
