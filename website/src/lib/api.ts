export async function authorizedFetch(url: string, options: RequestInit = {}) {
  const token = localStorage.getItem("access_token");

  const headers = {
    ...options.headers,
    "Authorization": `Bearer ${token}`,
    "Content-Type": "application/json"
  };

  const response = await fetch(url, { ...options, headers });

  // Handle expired tokens (401 Unauthorized)
  if (response.status === 401) {
    // Here you would typically try to use the refresh_token 
    // or redirect back to login
    localStorage.clear();
    window.location.href = "/login";
  }

  return response;
}
