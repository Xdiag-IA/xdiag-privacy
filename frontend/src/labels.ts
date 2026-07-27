// Frontend mirror of backend/app/pii.py LABEL_COLOR. Keep in sync.
// Used by DocumentViewer and EntityList to color entity overlays consistently
// regardless of whether the backend explicitly returns a color hint.

export const LABEL_COLORS: Record<string, string> = {
  BR_DOC: "#dc2626",
  BR_CPF: "#dc2626",
  CPF: "#dc2626",
  BR_CNPJ: "#ea580c",
  CNPJ: "#ea580c",
  BR_RG: "#d97706",
  RG: "#d97706",
  PERSON: "#f43f5e",
  PATIENT: "#f43f5e",
  PATIENT_NAME: "#f43f5e",
  DOCTOR: "#be185d",
  DOCTOR_NAME: "#be185d",
  PROFESSIONAL: "#db2777",
  DATE: "#2563eb",
  DATE_OF_BIRTH: "#1d4ed8",
  DOB: "#1d4ed8",
  AGE: "#0891b2",
  PHONE: "#16a34a",
  PHONE_NUMBER: "#16a34a",
  EMAIL: "#0d9488",
  ADDRESS: "#9333ea",
  STREET_ADDRESS: "#9333ea",
  CITY: "#7c3aed",
  STATE: "#6d28d9",
  ZIP: "#4f46e5",
  ZIPCODE: "#4f46e5",
  POSTAL_CODE: "#4f46e5",
  ID: "#4338ca",
  MEDICAL_RECORD: "#3730a3",
  MEDICAL_RECORD_NUMBER: "#3730a3",
  MRN: "#3730a3",
  CRM: "#db2777",
  INSTITUTION: "#475569",
  HOSPITAL: "#475569",
  ORGANIZATION: "#475569",
  URL: "#0369a1",
  IP: "#075985",
};

const FRIENDLY: Record<string, string> = {
  BR_DOC: "Documento",
  BR_CPF: "CPF",
  CPF: "CPF",
  BR_CNPJ: "CNPJ",
  CNPJ: "CNPJ",
  BR_RG: "RG",
  RG: "RG",
  PERSON: "Nome",
  PATIENT: "Paciente",
  PATIENT_NAME: "Paciente",
  DOCTOR: "Medico",
  DOCTOR_NAME: "Medico",
  PROFESSIONAL: "Profissional",
  DATE: "Data",
  DATE_OF_BIRTH: "Data de nascimento",
  DOB: "Data de nascimento",
  AGE: "Idade",
  PHONE: "Telefone",
  PHONE_NUMBER: "Telefone",
  EMAIL: "Email",
  ADDRESS: "Endereco",
  STREET_ADDRESS: "Endereco",
  CITY: "Cidade",
  STATE: "UF",
  ZIP: "CEP",
  ZIPCODE: "CEP",
  POSTAL_CODE: "CEP",
  ID: "Identificador",
  MEDICAL_RECORD: "Prontuario",
  MEDICAL_RECORD_NUMBER: "Prontuario",
  MRN: "Prontuario",
  CRM: "CRM",
  INSTITUTION: "Instituicao",
  HOSPITAL: "Hospital",
  ORGANIZATION: "Organizacao",
  URL: "URL",
  IP: "IP",
};

export function labelFriendly(label: string): string {
  const key = label.toUpperCase();
  return FRIENDLY[key] ?? label;
}

export function labelColor(label: string): string {
  return LABEL_COLORS[label.toUpperCase()] ?? "#dc2626";
}

export function maskText(text: string): string {
  // Keep only the first 2 and last 2 characters; mask the middle.
  if (text.length <= 4) return "*".repeat(text.length);
  return `${text.slice(0, 2)}${"*".repeat(Math.max(text.length - 4, 1))}${text.slice(-2)}`;
}
