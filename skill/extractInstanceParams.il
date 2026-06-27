; =====================================================================
; extractInstanceParams.il
; DTrace - schematic checkpoint extraction for Cadence Virtuoso
;
; Purpose:
;   Extract top-level schematic instance parameters into a CSV checkpoint
;   and invoke the Python parser to create a structured JSON snapshot.
;
; Provides:
;   extractInstanceParams()
;       Manual mode. Uses the active schematic window.
;
;   extractInstanceParamsFromLCV(libName cellName viewName)
;       Automatic mode. Opens schematic by lib/cell/view.
;       Intended for use from the ADE XL DTrace run flow.
;
; Notes:
;   - Configure DTRACE_BASE_DIR and DTRACE_SCHEMATIC_TOOL_PATH below
;     before loading this file in Cadence.
;   - Current implementation captures top-level instances only.
;   - MOS filtering is written for gpdk090-style nmos1v / pmos1v devices.
; =====================================================================

; =====================================================================
; User configuration
; =====================================================================

DTRACE_BASE_DIR = "/home/<user>/design_tracker/"
DTRACE_SCHEMATIC_TOOL_PATH = "/home/<user>/DTrace/python/schematic_tool.py"

; =====================================================================
; Core extractor: takes a cellview object directly
; =====================================================================
procedure( extractInstanceParamsFromCV(cv)
prog( (outPath outPort inst cdfId paramList p
pName pVal libName cellName viewName instName rowCount
wantedParams mosCellNames isMosDevice
pythonScriptPath logPath cmd status
baseDir checkpointDir tmpNumFile lastNumStr lastNum nextNum
numStr checkpointBase mkdirCmd numCmd inPort jsonPath)

```
pythonScriptPath = DTRACE_SCHEMATIC_TOOL_PATH

baseDir = DTRACE_BASE_DIR
checkpointDir = strcat(baseDir "checkpoints/")

wantedParams = '("model" "m" "l" "w" "fw" "fingers")
mosCellNames = '("nmos1v" "pmos1v")

unless( cv
    printf("ERROR: extractInstanceParamsFromCV received nil cellview.\n")
    return(nil)
)

unless( cv~>cellViewType == "schematic" || cv~>viewType == "schematic"
    printf("WARNING: Current cellview view type is '%s', not 'schematic'.\n"
           cv~>viewType)
    printf("         Proceeding anyway.\n")
)

printf("DTrace: extracting schematic %s %s %s\n"
       cv~>libName cv~>cellName cv~>viewName)

mkdirCmd = strcat("mkdir -p " checkpointDir)
system(mkdirCmd)

tmpNumFile = strcat(checkpointDir ".lastnum.tmp")

numCmd = strcat(
    "ls -1 " checkpointDir "checkpoint_*.csv 2>/dev/null | "
    "sed -n 's/.*checkpoint_\\([0-9]*\\)\\.csv/\\1/p' | "
    "sort -n | tail -1 > " tmpNumFile
)
system(numCmd)

lastNumStr = ""
inPort = infile(tmpNumFile)
when( inPort
    lastNumStr = gets(lastNumStr inPort)
    close(inPort)
)

unless( lastNumStr
    lastNumStr = ""
)

if( lastNumStr == "" then
    lastNum = 0
else
    lastNum = fix(atof(lastNumStr))
)

nextNum = lastNum + 1
sprintf(numStr "%04d" nextNum)
checkpointBase = strcat("checkpoint_" numStr)

outPath = strcat(checkpointDir checkpointBase ".csv")
outPort = outfile(outPath "w")

unless( outPort
    printf("ERROR: Could not open output file for writing: %s\n" outPath)
    return(nil)
)

fprintf(outPort "instance_name,lib_name,cell_name,view_name,param_name,param_value\n")

rowCount = 0

foreach( inst cv~>instances

    instName  = inst~>name
    libName   = inst~>libName
    cellName  = inst~>cellName
    viewName  = inst~>viewName

    isMosDevice = member(cellName mosCellNames)
    cdfId = cdfGetInstCDF(inst)

    cond(
        ( cdfId
            paramList = cdfId~>parameters

            if( paramList then
                foreach( p paramList
                    pName = p~>name

                    when( isMosDevice == nil || member(pName wantedParams)

                        pVal = p~>value

                        unless( pVal
                            pVal = ""
                        )

                        fprintf(outPort "%s,%s,%s,%s,%s,%L\n"
                            instName libName cellName viewName pName pVal)

                        rowCount = rowCount + 1
                    )
                )
            else
                fprintf(outPort "%s,%s,%s,%s,%s,%s\n"
                    instName libName cellName viewName "NO_PARAMS" "")
                rowCount = rowCount + 1
            )
        )
        ( t
            fprintf(outPort "%s,%s,%s,%s,%s,%s\n"
                instName libName cellName viewName "NO_CDF" "")
            rowCount = rowCount + 1
        )
    )
)

close(outPort)

logPath = strcat(outPath ".parselog.txt")
jsonPath = strcat(checkpointDir checkpointBase ".json")

cmd = strcat(
    "/usr/bin/python " pythonScriptPath " " outPath " > " logPath " 2>&1"
)

status = system(cmd)

printf("\n==================================================\n")

if( status == 0 then
    printf("DTrace: created checkpoint %s\n" numStr)
    printf("CSV : %s\n" outPath)
    printf("JSON: %s\n" jsonPath)
else
    printf("DTrace: checkpoint CSV created, but Python parse step FAILED (exit %L).\n"
           status)
    printf("CSV : %s\n" outPath)
    printf("Check log: %s\n" logPath)
)

printf("Instances processed : %d\n" length(cv~>instances))
printf("CSV rows written     : %d\n" rowCount)
printf("==================================================\n")

return(checkpointBase)
)
```

)

; =====================================================================
; Manual mode: active schematic window
; =====================================================================
procedure( extractInstanceParams()
prog( (cv win)

```
win = hiGetCurrentWindow()

unless( win
    printf("ERROR: No open window found. Open a schematic first.\n")
    return(nil)
)

cv = geGetEditCellView()

unless( cv
    printf("ERROR: No editable cellview found in current window.\n")
    printf("       Make sure a schematic is open and active.\n")
    return(nil)
)

extractInstanceParamsFromCV(cv)
)
```

)

; =====================================================================
; Automatic mode: open schematic by lib/cell/view
; Used by the ADE XL DTrace run flow.
; =====================================================================
procedure( extractInstanceParamsFromLCV(libName cellName viewName)
prog( (cv checkpointBase)

```
unless( viewName
    viewName = "schematic"
)

printf("DTrace: opening schematic %s %s %s\n" libName cellName viewName)

cv = dbOpenCellViewByType(libName cellName viewName "" "r")

unless( cv
    printf("ERROR: Could not open schematic: %s %s %s\n"
           libName cellName viewName)
    return(nil)
)

checkpointBase = extractInstanceParamsFromCV(cv)

dbClose(cv)

return(checkpointBase)
)
```

)
