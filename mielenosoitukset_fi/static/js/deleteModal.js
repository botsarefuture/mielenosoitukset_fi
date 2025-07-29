// Fast delete mode flag
let fastDeleteMode = false;

// Enable/disable fast delete on Shift key press/release
document.addEventListener('keydown', (e) => {
  if (e.key === 'Shift') {
    fastDeleteMode = true;
    updateDeleteButtonTexts();
    console.log('Fast delete mode enabled.');
  }
  if (e.key === 'Escape') {
    closeModal();
    console.log('Modal closed via Escape.');
  }
});

document.addEventListener('keyup', (e) => {
  if (e.key === 'Shift') {
    fastDeleteMode = false;
    updateDeleteButtonTexts();
    console.log('Fast delete mode disabled.');
  }
});

// Open modal or fast delete
function openModal(event, title, id, type = 'recu') {
  event.preventDefault();
  if (fastDeleteMode) {
    // Fast delete directly
    if (type === 'recu') {
      removeRecurringDemo(id);
    } else if (type === 'demo') {
      removeDemo(id);
    } else {
      alert('Virhe: Tuntematon tyyppi pikapoistossa.');
    }
  } else {
    // Show modal and fill in data
    document.getElementById('demoTitle').textContent = title;
    const confirmBtn = document.getElementById('confirmDelete');
    confirmBtn.dataset.id = id;
    confirmBtn.dataset.type = type;
    document.getElementById('deleteModal').classList.remove('hidden');
  }
}

// Close modal function
function closeModal() {
  document.getElementById('deleteModal').classList.add('hidden');
  const confirmBtn = document.getElementById('confirmDelete');
  confirmBtn.dataset.id = '';
  confirmBtn.dataset.type = '';
}

// Confirm delete button handler
document.getElementById('confirmDelete').addEventListener('click', () => {
  const confirmBtn = document.getElementById('confirmDelete');
  const id = confirmBtn.dataset.id;
  const type = confirmBtn.dataset.type;

  if (!id || !type) {
    alert('Virhe: poistettavaa kohdetta ei löytynyt.');
    return;
  }

  if (type === 'recu') {
    removeRecurringDemo(id);
  } else if (type === 'demo') {
    removeDemo(id);
  } else if (type === 'user') {
    removeUser(id);
  } else {
    alert('Virhe: tuntematon poistotyyppi.');
  }
});

function removeUser(id) {
  fetch('/admin/user/delete_user', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: id })
  })
    .then(res => res.json())
    .then(data => {
      if (data.status === 'OK') {
        const row = document.getElementById(`user-${id}`);
        if (row) row.remove();
        closeModal();
      } else {
        alert(data.message || 'Virhe poistettaessa käyttäjää.');
      }
    })
    .catch(() => alert('Yhteysvirhe, yritä uudelleen.'));
}

// Remove recurring demo
function removeRecurringDemo(id) {
  fetch(`/admin/recu_demo/delete_recu_demo/${id}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  })
    .then(res => res.json())
    .then(data => {
      if (data.status === 'OK') {
        const row = document.getElementById(`recu-demo-${id}`);
        if (row) row.remove();
        closeModal();
      } else {
        alert(data.message || 'Virhe poistettaessa.');
      }
    })
    .catch(() => alert('Yhteysvirhe, yritä uudelleen.'));
}

// Remove normal demo
function removeDemo(id) {
  fetch(`/admin/demo/delete_demo/${id}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  })
    .then(res => res.json())
    .then(data => {
      if (data.status === 'OK') {
        const row = document.getElementById(`demo-${id}`);
        if (row) row.remove();
        closeModal();
      } else {
        alert(data.message || 'Virhe poistettaessa.');
      }
    })
    .catch(() => alert('Yhteysvirhe, yritä uudelleen.'));
}

// Update delete button text based on fast delete mode
function updateDeleteButtonTexts() {
  const buttons = document.querySelectorAll('.delete-button');
  buttons.forEach(btn => {
    btn.textContent = fastDeleteMode ? 'Pikapoisto' : 'Poista';
  });
}

// Shake modal on outside click
window.onclick = function (event) {
  const modal = document.getElementById('deleteModal');
  if (event.target === modal) {
    shakeModal();
  }
};

function shakeModal() {
  const modalContent = document.querySelector('.modal-content');
  modalContent.classList.add('shake');
  setTimeout(() => {
    modalContent.classList.remove('shake');
  }, 500);
}
