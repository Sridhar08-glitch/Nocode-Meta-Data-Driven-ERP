/**
 * Payroll Engine client (Phase P2.8) — a NATIVE engine over `/api/v1/payroll/` (backend done).
 * Salary structures + components, employee assignments/profiles/contracts, pay periods + runs with
 * a server-enforced lifecycle (calculate → approve → post → lock) and segregation of duties, payslips
 * (immutable once posted), loans/advances/overtime/adjustments, and final settlements. The heavy math
 * (component calc, taxes, GL posting, SoD) runs server-side; this client drives the flows.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export type PayFrequency = "weekly" | "biweekly" | "semimonthly" | "monthly";
export type ComponentType = "earning" | "deduction" | "benefit";
export type CalcType = "fixed" | "formula" | "percent";
export type StructureStatus = "draft" | "active" | "archived";
export type PeriodStatus = "draft" | "open" | "processing" | "closed" | "locked";
export type RunStatus =
  | "draft"
  | "processing"
  | "completed"
  | "approved"
  | "posted"
  | "cancelled"
  | "locked";
export type AdjustmentType = "bonus" | "correction" | "one_time" | "deduction" | "recovery";

export interface PayrollSettings {
  frequency: PayFrequency | string;
  currency: string;
  default_country: string;
  default_cost_center: string;
  pay_start_day: number;
  pay_end_day: number;
}

export interface SalaryStructure {
  id: string;
  name: string;
  currency: string;
  country: string;
  effective_date: string;
  status: StructureStatus | string;
}

export interface SalaryComponent {
  id: string;
  salary_structure_id: string;
  code: string;
  name: string;
  component_type: ComponentType;
  calc_type: CalcType;
  amount: string;
  formula: string;
  base_code: string;
  formula_version: number;
  taxable: boolean;
  gl_account_code: string;
  sequence: number;
}

export interface SalaryAssignment {
  id: string;
  employee_record_id: string;
  salary_structure_id: string;
  effective_date: string;
  base_salary: string;
  is_current: boolean;
}

export interface PayrollProfile {
  id: string;
  employee_record_id: string;
  [key: string]: unknown;
}

export interface EmploymentContract {
  id: string;
  employee_record_id: string;
  [key: string]: unknown;
}

export interface PayPeriod {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  status: PeriodStatus | string;
}

export interface PayrollRun {
  id: string;
  payroll_period_id: string;
  status: RunStatus | string;
  total_gross: string;
  total_deductions: string;
  total_net: string;
  employee_count: number;
  journal_entry_id: string | null;
}

export interface PayslipLine {
  code: string;
  name: string;
  component_type: ComponentType | string;
  amount: string;
  source: string;
  sequence: number;
}

export interface Payslip {
  id: string;
  payroll_run_id: string;
  employee_record_id: string;
  total_gross: string;
  total_deductions: string;
  total_net: string;
  status: string;
  lines?: PayslipLine[];
}

export interface RegisterRow {
  payslip_id: string;
  employee_record_id: string;
  total_gross: string;
  total_deductions: string;
  total_net: string;
  [key: string]: unknown;
}

export interface RunSummary {
  total_gross: string;
  total_deductions: string;
  total_net: string;
  employee_count: number;
  [key: string]: unknown;
}

export interface Loan {
  id: string;
  employee_record_id: string;
  amount: string;
  installment: string;
  reference: string;
  balance: string;
  status: string;
}

export interface Advance {
  id: string;
  employee_record_id: string;
  amount: string;
  installment: string;
  reference: string;
  balance: string;
  status: string;
}

export interface Overtime {
  id: string;
  employee_record_id: string;
  hours: string;
  rate: string;
  multiplier: string;
  status: string;
}

export interface Adjustment {
  id: string;
  employee_record_id: string;
  adj_type: AdjustmentType | string;
  amount: string;
  name: string;
  status: string;
}

export interface FinalSettlement {
  employee_record_id: string;
  total: string;
  [key: string]: unknown;
}

const P = "/api/v1/payroll";

function qs(params: Record<string, string | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v) q.set(k, v);
  const s = q.toString();
  return s ? `?${s}` : "";
}

export const payrollApi = {
  // settings + setup
  getSettings: () => apiGet<PayrollSettings>(`${P}/settings/`),
  updateSettings: (data: Partial<PayrollSettings>) =>
    apiSend<PayrollSettings>(`${P}/settings/`, "PATCH", data),
  setup: () => apiSend<{ detail: string }>(`${P}/setup/`, "POST", {}),

  // salary structures + components
  listStructures: () => apiGet<SalaryStructure[]>(`${P}/salary-structures/`),
  createStructure: (data: Partial<SalaryStructure>) =>
    apiSend<SalaryStructure>(`${P}/salary-structures/`, "POST", data),
  getStructure: (id: string) => apiGet<SalaryStructure>(`${P}/salary-structures/${id}/`),
  updateStructure: (id: string, data: Partial<SalaryStructure>) =>
    apiSend<SalaryStructure>(`${P}/salary-structures/${id}/`, "PATCH", data),

  listComponents: (structureId: string) =>
    apiGet<SalaryComponent[]>(`${P}/components/${qs({ salary_structure_id: structureId })}`),
  createComponent: (data: Partial<SalaryComponent>) =>
    apiSend<SalaryComponent>(`${P}/components/`, "POST", data),
  updateComponent: (id: string, data: Partial<SalaryComponent>) =>
    apiSend<SalaryComponent>(`${P}/components/${id}/`, "PATCH", data),

  // assignments / profiles / contracts
  listAssignments: (employeeRecordId?: string) =>
    apiGet<SalaryAssignment[]>(`${P}/assignments/${qs({ employee_record_id: employeeRecordId })}`),
  createAssignment: (data: Partial<SalaryAssignment>) =>
    apiSend<SalaryAssignment>(`${P}/assignments/`, "POST", data),
  listProfiles: () => apiGet<PayrollProfile[]>(`${P}/profiles/`),
  createProfile: (data: Record<string, unknown>) =>
    apiSend<PayrollProfile>(`${P}/profiles/`, "POST", data),
  listContracts: () => apiGet<EmploymentContract[]>(`${P}/contracts/`),
  createContract: (data: Record<string, unknown>) =>
    apiSend<EmploymentContract>(`${P}/contracts/`, "POST", data),

  // periods + lifecycle
  listPeriods: () => apiGet<PayPeriod[]>(`${P}/periods/`),
  createPeriod: (data: Partial<PayPeriod>) => apiSend<PayPeriod>(`${P}/periods/`, "POST", data),
  getPeriod: (id: string) => apiGet<PayPeriod>(`${P}/periods/${id}/`),
  updatePeriod: (id: string, data: Partial<PayPeriod>) =>
    apiSend<PayPeriod>(`${P}/periods/${id}/`, "PATCH", data),
  openPeriod: (id: string) => apiSend<PayPeriod>(`${P}/periods/${id}/open/`, "POST", {}),
  closePeriod: (id: string) => apiSend<PayPeriod>(`${P}/periods/${id}/close/`, "POST", {}),
  lockPeriod: (id: string) => apiSend<PayPeriod>(`${P}/periods/${id}/lock/`, "POST", {}),
  reopenPeriod: (id: string) => apiSend<PayPeriod>(`${P}/periods/${id}/reopen/`, "POST", {}),

  // runs + lifecycle
  listRuns: (params?: { payroll_period_id?: string; status?: string }) =>
    apiGet<PayrollRun[]>(`${P}/runs/${qs(params ?? {})}`),
  createRun: (payrollPeriodId: string) =>
    apiSend<PayrollRun>(`${P}/runs/create/`, "POST", { payroll_period_id: payrollPeriodId }),
  getRun: (id: string) => apiGet<PayrollRun>(`${P}/runs/${id}/`),
  calculateRun: (id: string) => apiSend<PayrollRun>(`${P}/runs/${id}/calculate/`, "POST", {}),
  approveRun: (id: string) => apiSend<PayrollRun>(`${P}/runs/${id}/approve/`, "POST", {}),
  postRun: (id: string) => apiSend<PayrollRun>(`${P}/runs/${id}/post/`, "POST", {}),
  lockRun: (id: string) => apiSend<PayrollRun>(`${P}/runs/${id}/lock/`, "POST", {}),
  runRegister: (id: string) => apiGet<{ rows: RegisterRow[] }>(`${P}/runs/${id}/register/`),
  runSummary: (id: string) => apiGet<RunSummary>(`${P}/runs/${id}/summary/`),

  // payslips (read-only)
  listPayslips: (params?: { payroll_run_id?: string; employee_record_id?: string }) =>
    apiGet<Payslip[]>(`${P}/payslips/${qs(params ?? {})}`),
  getPayslip: (id: string) => apiGet<Payslip>(`${P}/payslips/${id}/`),

  // loans / advances / overtime / adjustments
  listLoans: () => apiGet<Loan[]>(`${P}/loans/`),
  createLoan: (data: Record<string, unknown>) => apiSend<Loan>(`${P}/loans/`, "POST", data),
  listAdvances: () => apiGet<Advance[]>(`${P}/advances/`),
  createAdvance: (data: Record<string, unknown>) =>
    apiSend<Advance>(`${P}/advances/`, "POST", data),
  listOvertime: () => apiGet<Overtime[]>(`${P}/overtime/list/`),
  createOvertime: (data: Record<string, unknown>) =>
    apiSend<Overtime>(`${P}/overtime/`, "POST", data),
  approveOvertime: (id: string) => apiSend<Overtime>(`${P}/overtime/${id}/approve/`, "POST", {}),
  listAdjustments: () => apiGet<Adjustment[]>(`${P}/adjustments/list/`),
  createAdjustment: (data: Record<string, unknown>) =>
    apiSend<Adjustment>(`${P}/adjustments/`, "POST", data),

  // final settlement
  createFinalSettlement: (data: Record<string, unknown>) =>
    apiSend<FinalSettlement>(`${P}/final-settlements/`, "POST", data),
};
