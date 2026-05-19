export function formatTime(value: string | Date): string {
  const date = value instanceof Date ? value : new Date(value);
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function formatPlayerName(name: string, isAI: boolean): string {
  return isAI ? `${name}（AI）` : name;
}
