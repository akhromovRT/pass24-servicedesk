const BASE_URL = ''

function getToken(): string | null {
  return localStorage.getItem('access_token')
}

export function setToken(token: string): void {
  localStorage.setItem('access_token', token)
}

export function clearToken(): void {
  localStorage.removeItem('access_token')
}

export function isAuthenticated(): boolean {
  return !!getToken()
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    // Явный Accept: application/json — гарантирует, что backend SPA-fallback
    // middleware (для /tickets/<uuid>, /projects/<uuid>) не подменит ответ
    // на index.html в случае, если запрос ушёл без Authorization (например,
    // токен ещё не подгрузился из localStorage).
    'Accept': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  }

  const token = getToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (response.status === 401) {
    // Редиректим на логин только если токен был — значит, сессия истекла.
    // Для анонимного пользователя просто пробрасываем ошибку: вызывающий код
    // сам решит, что делать (см. CustomerSelect.search), и SPA-состояние формы
    // не теряется из-за случайного обращения к защищённому эндпоинту.
    if (token) {
      clearToken()
      window.location.href = '/login'
    }
    throw new Error('Unauthorized')
  }

  if (response.status === 204) {
    return undefined as T
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Ошибка сервера' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  // Защита от случая, когда сервер ответил 200 с HTML вместо JSON (SPA-fallback
  // middleware ошибочно перехватил AJAX-запрос — токен протух). Сужаем строго
  // до Content-Type: text/html, чтобы не ловить пустые 200, plain-text ответы
  // и прочие штатные сценарии.
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('text/html')) {
    if (token) {
      clearToken()
      window.location.href = '/login'
    }
    throw new Error('Unexpected HTML response (token expired?)')
  }

  return response.json()
}

export const api = {
  get: <T>(path: string) => request<T>(path),

  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),

  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: body ? JSON.stringify(body) : undefined }),

  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body ? JSON.stringify(body) : undefined }),

  delete: <T>(path: string) =>
    request<T>(path, { method: 'DELETE' }),
}
