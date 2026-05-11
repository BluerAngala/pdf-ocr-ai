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
}

export default function ConfigPanel({
  moduleType,
  sampleRoot,
  excelFile,
  mockMode,
  forceOcr,
  running,
  printerName,
  printCopies,
  printers,
  onSampleRootChange,
  onExcelFileChange,
  onMockModeChange,
  onForceOcrChange,
  onPrinterNameChange,
  onPrintCopiesChange,
  onPreset,
  onSelectFolder,
  onSelectExcel,
  onRun,
}: Props) {
  switch (moduleType) {
    case "non-litigation":
      return (
        <NonLitigationConfig
          sampleRoot={sampleRoot}
          excelFile={excelFile}
          mockMode={mockMode}
          forceOcr={forceOcr}
          running={running}
          onSampleRootChange={onSampleRootChange}
          onExcelFileChange={onExcelFileChange}
          onMockModeChange={onMockModeChange}
          onForceOcrChange={onForceOcrChange}
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
          forceOcr={forceOcr}
          running={running}
          onSampleRootChange={onSampleRootChange}
          onExcelFileChange={onExcelFileChange}
          onForceOcrChange={onForceOcrChange}
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
          onExcelFileChange={onExcelFileChange}
          onPreset={onPreset}
          onSelectExcel={onSelectExcel}
          onRun={onRun}
        />
      );
    case "print":
      return (
        <PrintConfig
          sampleRoot={sampleRoot}
          printerName={printerName}
          printCopies={printCopies}
          printers={printers}
          running={running}
          onSampleRootChange={onSampleRootChange}
          onPrinterNameChange={onPrinterNameChange}
          onPrintCopiesChange={onPrintCopiesChange}
          onPreset={onPreset}
          onSelectFolder={onSelectFolder}
          onRun={onRun}
        />
      );
  }
}
