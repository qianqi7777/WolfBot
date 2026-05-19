import type { GameStatus, RoleType } from '@/types/game';

export function validateSpeakContent(content: string, maxLength = 200): boolean {
  return content.trim().length > 0 && content.length <= maxLength;
}

export function canVote(status: GameStatus): boolean {
  return status === 'vote';
}

export function canSpeak(status: GameStatus): boolean {
  return status === 'speak' || status === 'day';
}

export function canNightAction(status: GameStatus, role: RoleType): boolean {
  return status === 'night' && (role === 'wolf' || role === 'prophet' || role === 'guard');
}
