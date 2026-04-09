/**
 * Парсит дату из backend (UTC без timezone suffix) в Date объект.
 * Backend хранит datetime.utcnow() и отдаёт без 'Z':
 *   "2026-04-09T12:19:23.130845"
 * Без 'Z' JavaScript считает это локальным временем.
 * С 'Z' — корректно конвертирует UTC → локальное.
 */
export function parseUTC(dateStr: string): Date {
  if (!dateStr) return new Date()
  // Если уже есть timezone — не трогаем
  if (dateStr.endsWith('Z') || dateStr.includes('+') || /T\d{2}:\d{2}:\d{2}.*[+-]\d{2}/.test(dateStr)) {
    return new Date(dateStr)
  }
  return new Date(dateStr + 'Z')
}

/**
 * Форматирует дату из backend в локальное время.
 * "9 апр., 15:19" (по часовому поясу браузера)
 */
export function formatDate(dateStr: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parseUTC(dateStr))
}

/**
 * Форматирует дату полностью: "9 апреля 2026, 15:19"
 */
export function formatDateFull(dateStr: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parseUTC(dateStr))
}
