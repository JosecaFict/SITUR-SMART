/** Fechas de calendario de Bolivia, sin convertir el día elegido al huso del navegador. */
export function boliviaToday(now = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/La_Paz', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(now);
  const part = (type: string) => parts.find((item) => item.type === type)?.value ?? '';
  return `${part('year')}-${part('month')}-${part('day')}`;
}

export function addCalendarDays(day: string, offset: number): string {
  const date = new Date(`${day}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + offset);
  return date.toISOString().slice(0, 10);
}

export function calendarLabel(day: string, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat('es-BO', { ...options, timeZone: 'UTC' }).format(new Date(`${day}T12:00:00Z`));
}
