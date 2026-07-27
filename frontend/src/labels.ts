// Frontend mirror of backend/app/pii.py LABEL_COLOR. Keep in sync.
// Used by DocumentViewer and EntityList to color entity overlays consistently
// regardless of whether the backend explicitly returns a color hint.
//
// A paleta e organizada por FAMILIA de dado, nao por rotulo. A versao anterior
// tinha 40 tons, varios separados por um passo de luminancia (#4f46e5, #4338ca,
// #3730a3), indistinguiveis sobre o documento. Agora cada familia tem uma cor
// e o rotulo exato continua legivel no painel lateral. Todos os tons foram
// escolhidos para ter contraste sobre papel branco, que e o fundo real das
// tarjas. Vermelho puro nao aparece aqui: ele fica reservado para risco na
// interface (entidade nao mapeada, erro), para o alerta nao competir com a
// cor de uma categoria qualquer.

/** Familias de dado pessoal, na ordem em que aparecem na legenda. */
export const LABEL_FAMILY = {
  PACIENTE: "#db2777", // rosa: nome de pessoa / paciente
  PROFISSIONAL: "#be185d", // rosa escuro: nome de medico ou profissional
  DOCUMENTO: "#ea580c", // laranja: documento oficial (CPF, CNPJ, RG, CNS)
  REGISTRO: "#4f46e5", // indigo: prontuario e identificadores internos
  CONTATO: "#16a34a", // verde: telefone e email
  ENDERECO: "#7c3aed", // violeta: endereco, cidade, UF, CEP
  TEMPORAL: "#2563eb", // azul: datas e idade
  CONSELHO: "#0d9488", // teal: CRM, RQE, COREN
  INSTITUICAO: "#475569", // ardosia: hospital, clinica, CNES
  CONVENIO: "#a16207", // ouro escuro: guia, autorizacao, carteirinha
  REDE: "#0369a1", // azul profundo: URL e IP
  SUSPEITO: "#78716c", // pedra: numero suspeito nao classificado
  MANUAL: "#f59e0b", // ambar: area marcada a mao pelo operador
  OUTRO: "#c026d3", // fucsia: rotulo desconhecido, ainda assim tarjado
} as const;

const F = LABEL_FAMILY;

export const LABEL_COLORS: Record<string, string> = {
  BR_DOC: F.DOCUMENTO,
  BR_CPF: F.DOCUMENTO,
  CPF: F.DOCUMENTO,
  BR_CNPJ: F.DOCUMENTO,
  CNPJ: F.DOCUMENTO,
  BR_RG: F.DOCUMENTO,
  RG: F.DOCUMENTO,
  CNS: F.DOCUMENTO,
  PERSON: F.PACIENTE,
  PATIENT: F.PACIENTE,
  PATIENT_NAME: F.PACIENTE,
  DOCTOR: F.PROFISSIONAL,
  DOCTOR_NAME: F.PROFISSIONAL,
  PROFESSIONAL: F.PROFISSIONAL,
  DATE: F.TEMPORAL,
  DATE_OF_BIRTH: F.TEMPORAL,
  DOB: F.TEMPORAL,
  AGE: F.TEMPORAL,
  PHONE: F.CONTATO,
  PHONE_NUMBER: F.CONTATO,
  EMAIL: F.CONTATO,
  ADDRESS: F.ENDERECO,
  STREET_ADDRESS: F.ENDERECO,
  CITY: F.ENDERECO,
  STATE: F.ENDERECO,
  ZIP: F.ENDERECO,
  ZIPCODE: F.ENDERECO,
  POSTAL_CODE: F.ENDERECO,
  ID: F.REGISTRO,
  MEDICAL_RECORD: F.REGISTRO,
  MEDICAL_RECORD_NUMBER: F.REGISTRO,
  MRN: F.REGISTRO,
  CRM: F.CONSELHO,
  RQE: F.CONSELHO,
  COREN: F.CONSELHO,
  CNES: F.INSTITUICAO,
  INSTITUTION: F.INSTITUICAO,
  HOSPITAL: F.INSTITUICAO,
  ORGANIZATION: F.INSTITUICAO,
  TISS_GUIDE: F.CONVENIO,
  TISS_AUTH: F.CONVENIO,
  INSURANCE_ID: F.CONVENIO,
  URL: F.REDE,
  IP: F.REDE,
  NUMERO: F.SUSPEITO,
  MANUAL: F.MANUAL,
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
  DOCTOR: "Médico",
  DOCTOR_NAME: "Médico",
  PROFESSIONAL: "Profissional",
  DATE: "Data",
  DATE_OF_BIRTH: "Data de nascimento",
  DOB: "Data de nascimento",
  AGE: "Idade",
  PHONE: "Telefone",
  PHONE_NUMBER: "Telefone",
  EMAIL: "Email",
  ADDRESS: "Endereço",
  STREET_ADDRESS: "Endereço",
  CITY: "Cidade",
  STATE: "UF",
  ZIP: "CEP",
  ZIPCODE: "CEP",
  POSTAL_CODE: "CEP",
  ID: "Identificador",
  MEDICAL_RECORD: "Prontuário",
  MEDICAL_RECORD_NUMBER: "Prontuário",
  MRN: "Prontuário",
  CRM: "CRM",
  CNS: "CNS",
  CNES: "CNES",
  RQE: "RQE",
  COREN: "COREN",
  TISS_GUIDE: "Número de guia",
  TISS_AUTH: "Senha de autorização",
  INSURANCE_ID: "Carteirinha",
  NUMERO: "Número suspeito",
  INSTITUTION: "Instituição",
  HOSPITAL: "Hospital",
  ORGANIZATION: "Organização",
  URL: "URL",
  IP: "IP",
  MANUAL: "Manual",
};

export function labelFriendly(label: string): string {
  const key = label.toUpperCase();
  return FRIENDLY[key] ?? label;
}

export function labelColor(label: string): string {
  return LABEL_COLORS[label.toUpperCase()] ?? LABEL_FAMILY.OUTRO;
}

export function maskText(text: string): string {
  // Keep only the first 2 and last 2 characters; mask the middle.
  if (text.length <= 4) return "*".repeat(text.length);
  return `${text.slice(0, 2)}${"*".repeat(Math.max(text.length - 4, 1))}${text.slice(-2)}`;
}

/** rgba() a partir de um hex de 6 digitos, para preencher as tarjas. */
export function withAlpha(hex: string, alpha: number): string {
  const v = hex.replace("#", "");
  const r = parseInt(v.slice(0, 2), 16);
  const g = parseInt(v.slice(2, 4), 16);
  const b = parseInt(v.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
