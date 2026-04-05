/**
 * Стабильный session_id для анонимной телеметрии (KB feedback, deflection events).
 *
 * Хранится в localStorage, создаётся один раз при первом визите.
 * Используется для дедупликации отзывов: один session_id не может оставить
 * несколько feedback на одну статью.
 *
 * НЕ используется для аутентификации или персональных данных.
 */
const SESSION_KEY = 'pass24_session_id'

function generateUuid(): string {
  // Простой UUID v4 generator. Подходит для телеметрии (не для криптографии).
  // crypto.randomUUID доступен в современных браузерах.
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  // Fallback для старых браузеров
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

export function getSessionId(): string {
  try {
    let id = localStorage.getItem(SESSION_KEY)
    if (!id) {
      id = generateUuid()
      localStorage.setItem(SESSION_KEY, id)
    }
    return id
  } catch {
    // Privacy mode / storage disabled — возвращаем ephemeral UUID
    return generateUuid()
  }
}
