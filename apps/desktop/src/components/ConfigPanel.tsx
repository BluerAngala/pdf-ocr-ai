import type { ModuleType, PrinterInfo, PrintExcelColumn } from "../types";
import NonLitigationConfig from "./configs/NonLitigationConfig";
import EnforcementConfig from "./configs/EnforcementConfig";
import CompanyQueryConfig from "./configs/CompanyQueryConfig";
import PrintConfig from "./configs/PrintConfig";

interface Props {
  moduleType: ModuleType;
  sampleRoot: string;
  excelFile: string;
  mockMode: boolean;
  outputDir: string;

  running: boolean;
  cancelling: boolean;
  printerName: string;
  printCopies: number;
  printers: PrinterInfo[];
  onSampleRootChange: (v: string) => void;
  onExcelFileChange: (v: string) => void;
  onMockModeChange: (v: boolean) => void;
  onOutputDirChange: (v: string) => void;

  onPrinterNameChange: (v: string) => void;
  onPrintCopiesChange: (v: number) => void;
  onPreset: () => void;
  onSelectFolder: () => void;
  onSelectExcel: () => void;
  onSelectOutputDir: () => void;
  onRun: () => void;
  onCancel: () => void;
  onLoadCache: () => void;
  onClearCache: () => void;
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
  printCustomStartPage: number;
  onPrintCustomStartPageChange: (v: number) => void;
  printCustomEndPage: number;
  onPrintCustomEndPageChange: (v: number) => void;
  printExcelColumns: PrintExcelColumn[];
  onLoadExcelColumns: () => void;
  selectedPrintCount: number;
}

export default function ConfigPanel({
  moduleType,
  sampleRoot,
  excelFile,
  mockMode: _mockMode,
  outputDir,

  running,
  cancelling,
  printerName,
  printCopies,
  printers,
  onSampleRootChange,
  onExcelFileChange,
  onMockModeChange: _onMockModeChange,
  onOutputDirChange,

  onPrinterNameChange,
  onPrintCopiesChange,
  onPreset,
  onSelectFolder,
  onSelectExcel,
  onSelectOutputDir,
  onRun,
  onCancel,
  onLoadCache,
  onClearCache,
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
  printCustomStartPage,
  onPrintCustomStartPageChange,
  printCustomEndPage,
  onPrintCustomEndPageChange,
  printExcelColumns,
  onLoadExcelColumns,
  selectedPrintCount,
}: Props) {
  switch (moduleType) {
    case "non-litigation":
      return (
        <NonLitigationConfig
          sampleRoot={sampleRoot}
          excelFile={excelFile}
          outputDir={outputDir}
          running={running}
          cancelling={cancelling}
          onSampleRootChange={onSampleRootChange}
          onExcelFileChange={onExcelFileChange}
          onPreset={onPreset}
          onSelectFolder={onSelectFolder}
          onSelectExcel={onSelectExcel}
          onSelectOutputDir={onSelectOutputDir}
          onOutputDirChange={onOutputDirChange}
          onRun={onRun}
          onCancel={onCancel}
        />
      );
    case "enforcement":
      return (
        <EnforcementConfig
          sampleRoot={sampleRoot}
          excelFile={excelFile}
          outputDir={outputDir}
          running={running}
          cancelling={cancelling}
          onSampleRootChange={onSampleRootChange}
          onExcelFileChange={onExcelFileChange}
          onPreset={onPreset}
          onSelectFolder={onSelectFolder}
          onSelectExcel={onSelectExcel}
          onSelectOutputDir={onSelectOutputDir}
          onOutputDirChange={onOutputDirChange}
          onRun={onRun}
          onCancel={onCancel}
        />
      );
    case "company-query":
      return (
        <CompanyQueryConfig
          excelFile={excelFile}
          outputDir={outputDir}
          running={running}
          cancelling={cancelling}
          rangeStart={rangeStart}
          rangeEnd={rangeEnd}
          onExcelFileChange={onExcelFileChange}
          onRangeStartChange={onRangeStartChange}
          onRangeEndChange={onRangeEndChange}
          cacheTtlDays={cacheTtlDays}
          onCacheTtlDaysChange={onCacheTtlDaysChange}
          onPreset={onPreset}
          onSelectExcel={onSelectExcel}
          onSelectOutputDir={onSelectOutputDir}
          onOutputDirChange={onOutputDirChange}
          onRun={onRun}
          onCancel={onCancel}
          onLoadCache={onLoadCache}
          onClearCache={onClearCache}
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
          cancelling={cancelling}
          rangeStart={rangeStart}
          rangeEnd={rangeEnd}
          columnName={printCompanyNameColumn}
          excelColumns={printExcelColumns}
          printMode={printMode}
          customStartPage={printCustomStartPage}
          customEndPage={printCustomEndPage}
          onSampleRootChange={onSampleRootChange}
          onExcelFileChange={onExcelFileChange}
          onPrinterNameChange={onPrinterNameChange}
          onPrintCopiesChange={onPrintCopiesChange}
          onRangeStartChange={onRangeStartChange}
          onRangeEndChange={onRangeEndChange}
          onColumnNameChange={onPrintCompanyNameColumnChange}
          onPrintModeChange={onPrintModeChange}
          onCustomStartPageChange={onPrintCustomStartPageChange}
          onCustomEndPageChange={onPrintCustomEndPageChange}
          onPreset={onPreset}
          onSelectFolder={onSelectFolder}
          onSelectExcel={onSelectExcel}
          onRun={onRun}
          onCancel={onCancel}
          onLoadExcelColumns={onLoadExcelColumns}
          selectedPrintCount={selectedPrintCount}
        />
      );
  }
}
