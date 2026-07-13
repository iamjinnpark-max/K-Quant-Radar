// Boots the real Express app against the fakes and provides a fetch client
// with a per-instance cookie jar plus CSRF bootstrap, mirroring how the SPA
// talks to the service.

export async function startServer(buildApp) {
  const app = buildApp();
  const server = app.listen(0);
  await new Promise((resolve) => server.once("listening", resolve));
  const { port } = server.address();
  return {
    baseUrl: `http://127.0.0.1:${port}`,
    close: () => new Promise((resolve) => server.close(resolve)),
  };
}

export class Client {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
    this.cookies = new Map(); // name -> { value, maxAge|null }
    this.csrfToken = null;
  }

  cookieHeader() {
    return [...this.cookies.entries()]
      .map(([name, { value }]) => `${name}=${value}`)
      .join("; ");
  }

  storeCookies(response) {
    for (const raw of response.headers.getSetCookie()) {
      const [pair, ...attributes] = raw.split(";").map((part) => part.trim());
      const eq = pair.indexOf("=");
      const name = pair.slice(0, eq);
      const value = pair.slice(eq + 1);
      const maxAgeAttr = attributes.find((a) => a.toLowerCase().startsWith("max-age="));
      const maxAge = maxAgeAttr ? Number(maxAgeAttr.split("=")[1]) : null;
      if (value === "" || maxAge === 0) {
        this.cookies.delete(name);
      } else {
        this.cookies.set(name, { value, maxAge });
      }
    }
  }

  async bootstrapCsrf() {
    const response = await fetch(`${this.baseUrl}/auth/csrf`, {
      headers: { Cookie: this.cookieHeader() },
    });
    this.storeCookies(response);
    const body = await response.json();
    this.csrfToken = body.csrfToken;
  }

  async post(path, payload = {}, { csrf = true } = {}) {
    if (csrf && !this.csrfToken) {
      await this.bootstrapCsrf();
    }
    const headers = {
      "Content-Type": "application/json",
      Cookie: this.cookieHeader(),
    };
    if (csrf) {
      headers["x-csrf-token"] = this.csrfToken;
    }
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    this.storeCookies(response);
    return response;
  }

  async get(path) {
    const response = await fetch(`${this.baseUrl}${path}`, {
      headers: { Cookie: this.cookieHeader() },
    });
    this.storeCookies(response);
    return response;
  }
}
