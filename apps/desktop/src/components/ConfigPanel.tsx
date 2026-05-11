import type { ModuleType, PrinterInfo } from "../types";
import NonLitigationConfig from "./configs/NonLitigationConfig";
import EnforcementConfig from "./configs/EnforcementConfig";
import CompanyQueryConfig from "./configs/CompanyQueryConfig";
import PrintConfig from "./configs/PrintConfig";

interface Props {
  moduleType: ModuleType;
  sampleRoot: string;
  excelFile: string;
  mockMode: boolean;
  forceOcr: boolean;
  running: boolean;
  printerName: string;
  printCopies: number;
  printers: PrinterInfo[];
  onSampleRootChange: (v: string) => void;
  onExcelFileChange: (v: string) => void;
  onMockModeChange: (v: boolean) => void;
  onForceOcrChange: (v: boolean) => void;
  onPrinterNameChange: (v: string) => void;
  onPrintCopiesChange: (v: number) => void;
  onPreset: () => void;
  onSelectFolder: () => void;
  onSelectExcel: () => void;
  onRun: () => void;
  onCancel: () => void;
  onLoadCache: () => void;
  rangeStart: number;
  rangeEnd: number;
  onRangeStartChange: (v: number) => void;
  onRangeEndChange: (v: number) => void;
  cacheTtlDays: number;
  onCacheTtlDaysChange: (v: number) => void;
  // Print module specific
  printCompanyNameColumn: string;
  onPrintCompanyNameColumnChange: (v: string) => void;
  printMode: "single" | "double";
  onPrintModeChange: (v: "single" | "double") => void;
  printPageRange: "all" | "custom";
  onPrintPageRangeChange: (v: "all" | "custom") => void;
  printCustomStartPage: number;
  onPrintCustomStartPageChange: (v: number) => void;
  printCustomEndPage: number;
  onPrintCustomEndPageChange: (v: number) => void;
}

export default function ConfigPanel({
  moduleType,
  sampleRoot,
  excelFile,
  mockMode: _mockMode,
  forceOcr: _forceOcr,
  running,
  printerName,
  printCopies,
  printers,
  onSampleRootChange,
  onExcelFileChange,
  onMockModeChange: _onMockModeChange,
  onForceOcrChange: _onForceOcrChange,
  onPrinterNameChange,
  onPrintCopiesChange,
  onPreset,
  onSelectFolder,
  onSelectExcel,
  onRun,
  onCancel,
  onLoadCache,
  rangeStart,
  rangeEnd,
  onRangeStartChange,
  onRangeEndChange,
  cacheTtlDays,
  onCacheTtlDaysChange,
  // Print module specific
  printCompanyNameColumn,
  onPrintCompanyNameColumnChange,
  printMode,
  onPrintModeChange,
  printPageRange,
  onPrintPageRangeChange,
  printCustomStartPage,
  onPrintCustomStartPageChange,
  printCustomEndPage,
  onPrintCustomEndPageChange,
}: Props) {
  switch (moduleType) {
    case "non-litigation":
      return (
        <NonLitigationConfig
          sampleRoot={sampleRoot}
          excelFile={excelFile}
          running={running}
          onSampleRootChange={onSampleRootChange}
          onExcelFileChange={onExcelFileChange}
          onPreset={onPreset}
          onSelectFolder={onSelectFolder}
          onSelectExcel={onSelectExcel}
          onRun={onRun}
        />
      );
    case "enforcement":
      return (
        <EnforcementConfig
          sampleRoot={sampleRoot}
          excelFile={excelFile}
          forceOcr={_forceOcr}
          running={running}
          onSampleRootChange={onSampleRootChange}
          onExcelFileChange={onExcelFileChange}
          onForceOcrChange={_onForceOcrChange}
          onPreset={onPreset}
          onSelectFolder={onSelectFolder}
          onSelectExcel={onSelectExcel}
          onRun={onRun}
        />
      );
    case "company-query":
      return (
        <CompanyQueryConfig
          excelFile={excelFile}
          running={running}
          rangeStart={rangeStart}
          rangeEnd={rangeEnd}
          onExcelFileChange={onExcelFileChange}
          onRangeStartChange={onRangeStartChange}
          onRangeEndChange={onRangeEndChange}
          cacheTtlDays={cacheTtlDays}
          onCacheTtlDaysChange={onCacheTtlDaysChange}
          onPreset={onPreset}
          onSelectExcel={onSelectExcel}
          onRun={onRun}
          onCancel={onCancel}
          onLoadCache={onLoadCache}
        />
      );
    case "print":
      return (
        <PrintConfig
          sampleRoot={sampleRoot}
          excelFile={excelFile}
          printerName={printerName}
          printCopies={printCopies}
          printers={printers}
          running={running}
          rangeStart={rangeStart}
          rangeEnd={rangeEnd}
          companyNameColumn={printCompanyNameColumn}
          printMode={printMode}
          pageRange={printPageRange}
          customStartPage={printCustomStartPage}
          customEndPage={printCustomEndPage}
          onSampleRootChange={onSampleRootChange}
          onExcelFileChange={onExcelFileChange}
          onPrinterNameChange={onPrinterNameChange}
          onPrintCopiesChange={onPrintCopiesChange}
          onRangeStartChange={onRangeStartChange}
          onRangeEndChange={onRangeEndChange}
          onCompanyNameColumnChange={onPrintCompanyNameColumnChange}
          onPrintModeChange={onPrintModeChange}
          onPageRangeChange={onPrintPageRangeChange}
          onCustomStartPageChange={onPrintCustomStartPageChange}
          onCustomEndPageChange={onPrintCustomEndPageChange}
          onPreset={onPreset}
          onSelectFolder={onSelectFolder}
          onSelectExcel={onSelectExcel}
          onRun={onRun}
        />
      );
  }
}
