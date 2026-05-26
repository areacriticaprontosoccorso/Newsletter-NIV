exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method Not Allowed' };
  }

  const { email } = JSON.parse(event.body);
  if (!email) return { statusCode: 400, body: 'Email mancante' };

  const REPO = 'areacriticaprontosoccorso/newsletter-NIV';
  const TOKEN = process.env.GH_TOKEN;
  const FILE_PATH = 'subscribers.json';
  const API = `https://api.github.com/repos/${REPO}/contents/${FILE_PATH}`;

  const getRes = await fetch(API, {
    headers: { Authorization: `token ${TOKEN}`, Accept: 'application/vnd.github.v3+json' }
  });
  const fileData = await getRes.json();
  const sha = fileData.sha;
  const current = JSON.parse(Buffer.from(fileData.content, 'base64').toString('utf8'));

  if (current.find(s => s.email === email)) {
    return { statusCode: 200, body: JSON.stringify({ status: 'already_subscribed' }) };
  }

  current.push({ email, subscribed_at: new Date().toISOString() });
  const updated = Buffer.from(JSON.stringify(current, null, 2)).toString('base64');

  await fetch(API, {
    method: 'PUT',
    headers: { Authorization: `token ${TOKEN}`, Accept: 'application/vnd.github.v3+json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: `Subscribe: ${email}`, content: updated, sha })
  });

  return {
    statusCode: 200,
    headers: { 'Access-Control-Allow-Origin': '*' },
    body: JSON.stringify({ status: 'subscribed' })
  };
};
