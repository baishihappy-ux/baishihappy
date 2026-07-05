const fields = {
  machineCode: document.getElementById('machine-code'),
  validDays: document.getElementById('valid-days'),
  maxConcurrency: document.getElementById('max-concurrency'),
  doToken: document.getElementById('do-token'),
  code: document.getElementById('code'),
  message: document.getElementById('message')
};

document.getElementById('generate').addEventListener('click', async () => {
  const result = await window.authorizer.generate({
    machineCode: fields.machineCode.value,
    validDays: fields.validDays.value,
    maxConcurrency: fields.maxConcurrency.value,
    doToken: fields.doToken.value
  });
  if (!result.ok) {
    fields.message.textContent = result.error;
    return;
  }
  fields.code.value = result.code;
  fields.message.textContent = '授权码已生成';
});

document.getElementById('copy').addEventListener('click', async () => {
  if (!fields.code.value.trim()) return;
  await window.authorizer.copy(fields.code.value);
  fields.message.textContent = '授权码已复制';
});
