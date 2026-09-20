/**
 * WebAuthn (passkey) helpers shared by the login and settings pages.
 *
 * The server returns options already JSON-encoded (challenge, user, and
 * credential ids as base64url strings); the browser WebAuthn API needs
 * ArrayBuffers, so everything is converted centrally here.
 */

function bufToB64url(buf) {
  let str = "";
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i += 0x8000) {
    str += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  }
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function b64urlToBuffer(b64) {
  const b = b64.replace(/-/g, "+").replace(/_/g, "/");
  const pad = b.length % 4 ? "=".repeat(4 - (b.length % 4)) : "";
  const bin = atob(b + pad);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

function decodePublicKeyOptions(options) {
  const copy = JSON.parse(JSON.stringify(options));
  if (typeof copy.challenge === "string") copy.challenge = b64urlToBuffer(copy.challenge);
  if (copy.user && typeof copy.user.id === "string") copy.user.id = b64urlToBuffer(copy.user.id);
  ["allowCredentials", "excludeCredentials"].forEach((key) => {
    if (Array.isArray(copy[key])) {
      copy[key] = copy[key].map((d) =>
        d && typeof d.id === "string" ? Object.assign({}, d, { id: b64urlToBuffer(d.id) }) : d
      );
    }
  });
  return copy;
}

function formatRegistrationCredential(publicKeyCredential) {
  const response = publicKeyCredential.response;
  return {
    id: publicKeyCredential.id,
    rawId: publicKeyCredential.rawId ? bufToB64url(publicKeyCredential.rawId) : publicKeyCredential.id,
    type: publicKeyCredential.type,
    response: {
      clientDataJSON: bufToB64url(response.clientDataJSON),
      attestationObject: bufToB64url(response.attestationObject),
      transports:
        typeof response.getTransports === "function" ? response.getTransports() : []
    }
  };
}

function formatAssertionCredential(publicKeyCredential) {
  const response = publicKeyCredential.response;
  return {
    id: publicKeyCredential.id,
    rawId: publicKeyCredential.rawId ? bufToB64url(publicKeyCredential.rawId) : publicKeyCredential.id,
    type: publicKeyCredential.type,
    response: {
      clientDataJSON: bufToB64url(response.clientDataJSON),
      authenticatorData: bufToB64url(response.authenticatorData),
      signature: bufToB64url(response.signature),
      userHandle: response.userHandle ? bufToB64url(response.userHandle) : null
    }
  };
}

async function signInWithPasskey(username) {
  const optionsRes = await fetch("/users/auth/api/v2/passkeys/login/options", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: username || "" })
  });
  const optionsData = await optionsRes.json();
  if (optionsData.status !== "success") {
    throw new Error(optionsData.message || "Passkey-asetuksia ei saatu haettua");
  }

  const assertion = await navigator.credentials.get({
    publicKey: decodePublicKeyOptions(optionsData.options)
  });
  const credential = formatAssertionCredential(assertion);

  const verifyRes = await fetch("/users/auth/api/v2/passkeys/login/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential: credential })
  });
  const verifyData = await verifyRes.json();
  if (verifyData.status !== "success") {
    throw new Error(verifyData.message || "Kirjautuminen passkeyllä epäonnistui");
  }
  return verifyData.redirect || "/";
}

async function registerPasskey(name) {
  const optionsRes = await fetch("/users/auth/api/v2/passkeys/register/options", {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  });
  const optionsData = await optionsRes.json();
  if (optionsData.status !== "success") {
    throw new Error(optionsData.message || "Rekisteröintiasetuksia ei saatu haettua");
  }

  const publicKeyCredential = await navigator.credentials.create({
    publicKey: decodePublicKeyOptions(optionsData.options)
  });
  const credential = formatRegistrationCredential(publicKeyCredential);

  const verifyRes = await fetch("/users/auth/api/v2/passkeys/register/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential: credential, name: name || "Authenticator" })
  });
  const verifyData = await verifyRes.json();
  if (verifyData.status !== "success") {
    throw new Error(verifyData.message || "Passkeyn tallentaminen epäonnistui");
  }
  return verifyData.passkeys || [];
}