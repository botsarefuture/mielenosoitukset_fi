document.addEventListener("DOMContentLoaded", () => {
  const usernameInput = document.getElementById("username");
  const emailInput = document.getElementById("email");
  const usernameStatus = document.getElementById("username-status");
  const passwordInput = document.getElementById("password");
  const confirmInput = document.getElementById("password_confirm");
  const strengthFill = document.getElementById("strength-fill");
  const matchMessage = document.getElementById("password-match-message");
  const generateBtn = document.getElementById("generate-password");
  const pwdNowMissing = document.getElementById("pwd-now-missing");
  const reqLength = document.getElementById("req-length");
  const reqComplex = document.getElementById("req-complex");
  const reqNoUsername = document.getElementById("req-no-username");
  const allowedSpecials = "!@#$%^&*()-_=+[]{};:,.<>?";
  const specialRegex = /[!@#$%^&*()\-\_=+\[\]{};:,.<>?]/;

  // --- Toggle password visibility ---
  function setupToggle(toggleId, input) {
    const toggle = document.getElementById(toggleId);
    if (!toggle) return;
    toggle.addEventListener("click", () => {
      input.type = input.type === "password" ? "text" : "password";
      const icon = toggle.querySelector("i");
      icon.classList.toggle("fa-eye");
      icon.classList.toggle("fa-eye-slash");
    });
  }
  setupToggle("password-toggle-icon", passwordInput);
  setupToggle("password-confirm-toggle-icon", confirmInput);

  // --- Password strength ---
  function updateStrength() {
    const val = passwordInput.value;
    let score = 0;
    if (val.length >= 12) score++;
    if (/[a-z]/.test(val)) score++;
    if (/[A-Z]/.test(val)) score++;
    if (/[0-9]/.test(val)) score++;
    if (specialRegex.test(val)) score++;

    if (score <= 2) {
      strengthFill.className = "strength-meter-fill strength-weak";
      strengthFill.style.width = "33%";
    } else if (score <= 4) {
      strengthFill.className = "strength-meter-fill strength-medium";
      strengthFill.style.width = "66%";
    } else {
      strengthFill.className = "strength-meter-fill strength-strong";
      strengthFill.style.width = "100%";
    }
  }

  
  function checkMatch() {
    const matchIcon = matchMessage.querySelector('i');
    const matchText = matchMessage.querySelector('span');
    
    if (confirmInput.value === "") {
      matchIcon.className = "fa-solid fa-xmark";
      matchText.textContent = "{{ _('Salasanat eivät täsmää') }}";
      matchMessage.classList.remove("valid");
      return false;
    }
    
    if (passwordInput.value === confirmInput.value) {
      matchIcon.className = "fa-solid fa-check";
      matchText.textContent = "{{ _('Salasanat täsmäävät') }}";
      matchMessage.classList.add("valid");
      return true;
    } else {
      matchIcon.className = "fa-solid fa-xmark";
      matchText.textContent = "{{ _('Salasanat eivät täsmää') }}";
      matchMessage.classList.remove("valid");
      return false;
    }
  }

  // --- Password requirements ---
  function updateRequirements() {
    const pwd = passwordInput.value;
    const username = usernameInput.value.trim().toLowerCase();
    const email = emailInput.value.trim().toLowerCase();
    let missing = [];

    // Length
    if (pwd.length >= 12) reqLength.className = "valid";
    else { reqLength.className = "invalid"; missing.push("Vähintään 12 merkkiä pitkä"); }

    // Complexity
    let types = 0;
    if (/[a-z]/.test(pwd)) types++;
    if (/[A-Z]/.test(pwd)) types++;
    if (/[0-9]/.test(pwd)) types++;
    if (specialRegex.test(pwd)) types++;
    if (types >= 3) reqComplex.className = "valid";
    else { reqComplex.className = "invalid"; missing.push("Vähintään 3 eri merkkityyppiä"); }

    // No username/email
    const lowerPwd = pwd.toLowerCase();
    if (!username || (!lowerPwd.includes(username) && !lowerPwd.includes(email))) reqNoUsername.className = "valid";
    else { reqNoUsername.className = "invalid"; missing.push("Ei saa sisältää käyttäjätunnusta tai sähköpostia"); }

    // Display missing requirements
    if (missing.length === 0) {
      pwdNowMissing.innerHTML = "Kaikki vaatimukset täytetty! ✅";
      pwdNowMissing.classList.add("valid");
      pwdNowMissing.classList.remove("invalid");
    } else {
      pwdNowMissing.innerHTML = missing.map(m => "• " + m).join("<br>");
      pwdNowMissing.classList.add("invalid");
      pwdNowMissing.classList.remove("valid");
    }
  }

  // --- Generate random password ---
  function generatePassword(len = 16) {
    const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+[]{};:,.<>?";
    let pwd = "";
    for (let i = 0; i < len; i++) pwd += chars.charAt(Math.floor(Math.random() * chars.length));
    return pwd;
  }
  generateBtn.addEventListener("click", () => {
    const pwd = generatePassword();
    passwordInput.value = confirmInput.value = pwd;
    updateStrength();
    checkMatch();
    updateRequirements();
  });

  // --- Username availability (debounced) ---
  let usernameTimeout;
  usernameInput.addEventListener("input", () => {
    clearTimeout(usernameTimeout);
    const uname = usernameInput.value.trim();
    if (!uname) { usernameStatus.textContent = ""; return; }
    if (uname.length < 3) {
      usernameStatus.textContent = "Käyttäjätunnuksen on oltava vähintään 3 merkkiä pitkä ❌";
      usernameStatus.style.color = "#e74c3c";
      return;
    }
    usernameStatus.textContent = "Käyttäjätunnus on tarpeeksi pitkä ✅";
    usernameStatus.style.color = "#27ae60";

    usernameTimeout = setTimeout(async () => {
      try {
        const resp = await fetch(`/users/auth/api/username_free?username=${encodeURIComponent(uname)}`);
        const data = await resp.json();
        if (data.available) {
          usernameStatus.textContent = "Käyttäjätunnus on vapaa ✅";
          usernameStatus.style.color = "#27ae60";
        } else {
          usernameStatus.textContent = "Käyttäjätunnus on jo varattu ❌";
          usernameStatus.style.color = "#e74c3c";
        }
      } catch {
        usernameStatus.textContent = "Tarkistuksessa tapahtui virhe ⚠️";
        usernameStatus.style.color = "#f39c12";
      }
    }, 500);

    updateRequirements();
  });

  // --- Event listeners ---
  passwordInput.addEventListener("input", () => { updateStrength(); checkMatch(); updateRequirements(); });
  confirmInput.addEventListener("input", checkMatch);
  emailInput.addEventListener("input", updateRequirements);

  // --- Form submission ---
  document.getElementById("register-form").addEventListener("submit", e => {
    if (usernameStatus.textContent.includes("❌")) {
      e.preventDefault();
      alert("Käyttäjätunnus on jo varattu!");
    }
    if (passwordInput.value !== confirmInput.value) {
      e.preventDefault();
      alert("Salasanat eivät täsmää!");
    }
  });
});
