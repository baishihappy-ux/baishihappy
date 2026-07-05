const password = document.getElementById('password');
const message = document.getElementById('unlock-message');
const unlock = document.getElementById('unlock');

async function submit() {
  const result = await window.authorizer.unlock(password.value);
  if (!result.ok) {
    message.textContent = result.error || 'Invalid password.';
    password.select();
  }
}

unlock.addEventListener('click', submit);
password.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') submit();
});
