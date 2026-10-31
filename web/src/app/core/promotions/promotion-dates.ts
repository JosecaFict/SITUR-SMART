/** datetime-local represents Bolivia time; the browser may use a different zone. */
export function toBoliviaInput(instant: string): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/La_Paz', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(new Date(instant));
  const value = (type: string) => parts.find((part) => part.type === type)?.value ?? '';
  return `${value('year')}-${value('month')}-${value('day')}T${value('hour')}:${value('minute')}`;
}

export function fromBoliviaInput(value: string): string {
  return `${value}:00-04:00`;
}
