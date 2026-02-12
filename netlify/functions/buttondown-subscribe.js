export async function handler(event) {
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method Not Allowed" };
  }

  try {
    const contentType = event.headers["content-type"] || "";
    let email = "";

    // Handle form-encoded submissions
    if (contentType.includes("application/x-www-form-urlencoded")) {
      const params = new URLSearchParams(event.body || "");
      email = (params.get("email") || "").trim();
    } else {
      // Handle JSON submissions (optional)
      const body = JSON.parse(event.body || "{}");
      email = (body.email || "").trim();
    }

    if (!email) {
      return { statusCode: 400, body: "Missing email" };
    }

    // Forward to Buttondown's embed endpoint (server-side)
    const bdRes = await fetch("https://buttondown.com/api/emails/embed-subscribe/eosguidehub", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ email }).toString(),
    });

    // Buttondown often returns HTML/text, not always JSON
    const bdText = await bdRes.text();

    // Treat any 2xx as success
    if (bdRes.ok) {
      return {
        statusCode: 200,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ok: true }),
      };
    }

    return {
      statusCode: 400,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ok: false, error: bdText.slice(0, 300) }),
    };
  } catch (e) {
    return {
      statusCode: 500,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ok: false, error: e.message || "Server error" }),
    };
  }
}


