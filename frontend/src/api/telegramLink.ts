import { api } from './client'

export interface TelegramLinkToken {
  token: string
  deeplink: string
  expires_at: string  // ISO timestamp
}

export async function generateTelegramLinkToken(): Promise<TelegramLinkToken> {
  return api.post<TelegramLinkToken>('/auth/telegram/link-token')
}

export async function unlinkTelegram(): Promise<void> {
  await api.delete<{ ok: boolean }>('/auth/telegram/link')
}
