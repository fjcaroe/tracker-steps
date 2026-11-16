export type EmergencyContact = { name: string; phone: string };
export const MAX_EMERGENCY_CONTACTS = 3;

const storageKey = (userId: number) => `tracker-emergency-contacts:${userId}`;
const validPhone = (phone: string) => /^\+?\d{3,15}$/.test(phone);

export function getEmergencyContacts(userId: number): EmergencyContact[] {
  try {
    const data: unknown = JSON.parse(localStorage.getItem(storageKey(userId)) ?? '[]');
    if (!Array.isArray(data)) return [];
    return data.filter((item): item is EmergencyContact => Boolean(item)
      && typeof item.name === 'string' && typeof item.phone === 'string' && validPhone(item.phone))
      .slice(0, MAX_EMERGENCY_CONTACTS);
  } catch {
    return [];
  }
}

export function saveEmergencyContacts(userId: number, data: EmergencyContact[]): void {
  const contacts = data.map(({ name, phone }) => ({
    name: name.trim(), phone: phone.trim().replace(/[\s().-]/g, ''),
  })).filter(({ name, phone }) => name || phone);
  if (contacts.length > MAX_EMERGENCY_CONTACTS || contacts.some(({ phone }) => !validPhone(phone))) {
    throw new Error('Ingresa un teléfono válido para cada contacto. Puedes incluir el prefijo internacional.');
  }
  if (new Set(contacts.map(({ phone }) => phone)).size !== contacts.length) {
    throw new Error('Cada contacto debe tener un número distinto.');
  }
  localStorage.setItem(storageKey(userId), JSON.stringify(contacts));
}

export function emergencySmsLink(phone: string, fix: { lat: number; lon: number } | null): string {
  const location = fix ? ` Última ubicación del teléfono: https://maps.google.com/?q=${fix.lat},${fix.lon}` : '';
  const separator = /iPad|iPhone|iPod/.test(navigator.userAgent) ? '&' : '?';
  return `sms:${phone}${separator}body=${encodeURIComponent('Necesito ayuda.' + location)}`;
}
