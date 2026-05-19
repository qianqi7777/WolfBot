import type { GameStatus, Player, RoleType } from '@/types/game';
import { canNightAction as canNightActionState, canSpeak, canVote, validateSpeakContent } from '@/utils/validate';

export function useGameLogic() {
  const canPlayerSpeak = (status: GameStatus, player?: Player) => {
    return Boolean(player?.isAlive) && canSpeak(status);
  };

  const canPlayerVote = (status: GameStatus, player?: Player) => {
    return Boolean(player?.isAlive) && canVote(status);
  };

  const isValidSpeak = (content: string) => validateSpeakContent(content);

  const canPlayerNightAction = (status: GameStatus, role: RoleType, player?: Player) => {
    return Boolean(player?.isAlive) && canNightActionState(status, role);
  };

  return {
    canPlayerSpeak,
    canPlayerVote,
    canPlayerNightAction,
    isValidSpeak,
  };
}
