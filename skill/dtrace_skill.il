; =====================================================================
; dtrace_skill.il
; DTrace - ADE XL run integration for Cadence Virtuoso
;
; Purpose:
;   Provide the ADE XL entry point for DTrace.
;
;   The main flow:
;       1. Capture schematic checkpoint before simulation.
;       2. Capture ADE XL setup variables.
;       3. Mark checkpoint as pending.
;       4. Launch ADE XL simulation.
;       5. Export results after run completion.
;       6. Invoke Python completion flow.
;
; Dependencies:
;   - extractInstanceParams.il must be loaded before this file.
;   - dtrace.py must be available at DTRACE_PY.
;
; Notes:
;   - Configure DTRACE_BASE_DIR and DTRACE_PY below before use.
;   - This implementation targets ADE XL workflows.
;   - API behavior may vary across Cadence installations.
; =====================================================================

; =====================================================================
; User configuration
; =====================================================================

DTRACE_BASE_DIR = "/home/<user>/design_tracker/"
DTRACE_PY       = "/home/<user>/DTrace/python/dtrace.py"
DTRACE_LOG      = strcat(DTRACE_BASE_DIR "dtrace.log")

; =====================================================================
; Main DTrace run entry point
; Intended to be triggered from ADE XL.
; =====================================================================
procedure( dtraceRun()
prog( (session cmd runId)

```
session = axlGetWindowSession()

unless( session
    printf("ERROR: Open ADE XL window and start DTrace from ADE XL.\n")
    return(nil)
)

printf("DTrace: using ADE XL session: %s\n" session)

; Capture schematic before simulation begins.
let( (libName cellName checkpointId)
    libName  = axlGetSessionLibName(session)
    cellName = axlGetSessionCellName(session)

    checkpointId = extractInstanceParamsFromLCV(libName cellName "schematic")

    unless( checkpointId
        printf("ERROR: schematic checkpoint capture failed.\n")
        return(nil)
    )

    dtraceCaptureADEXLSetup(checkpointId)
)

; Mark latest schematic checkpoint as pending.
cmd = strcat(
    "/usr/bin/python " DTRACE_PY
    " set-pending >> " DTRACE_LOG " 2>&1"
)
system(cmd)

; Start ADE XL run with callback.
runId = axlRunAllTestsWithCallback(
    session
    "normal"
    "dtraceOnRunFinished()"
)

printf("DTrace: ADE XL run started. Run ID: %L\n" runId)

t
)
```

)

; =====================================================================
; ADE XL completion callback
; Called after simulation run finishes.
; =====================================================================
procedure( dtraceOnRunFinished()
let( (session csvPath cmd status)

```
session = axlGetWindowSession()
csvPath = strcat(DTRACE_BASE_DIR "adexl_results/dtrace_latest.csv")

printf("DTrace: ADE XL run finished. Exporting Detail view...\n")

status = axlExportOutputView(session csvPath "Detail")

printf("DTrace: export status: %L\n" status)

cmd = strcat(
    "xterm -e /usr/bin/python " DTRACE_PY
    " complete-csv "
    csvPath
    " --no-gui"
    " >> " DTRACE_LOG " 2>&1 &"
)

system(cmd)

printf("DTrace: Python completion launched.\n")

t
)
```

)

; =====================================================================
; Capture ADE XL setup variables for current checkpoint
; =====================================================================
procedure( dtraceCaptureADEXLSetup(checkpointId)
prog( (session setupDb vars outFile cmd port checkpointDir varName varObj val)

```
session = axlGetWindowSession()

unless( session
    printf("ERROR: no ADE XL session found while capturing setup.\n")
    return(nil)
)

setupDb = axlGetMainSetupDB(session)

checkpointDir = strcat(DTRACE_BASE_DIR "checkpoints/")
outFile = strcat(checkpointDir checkpointId "_adexl_vars.raw")

vars = axlGetVars(setupDb)

port = outfile(outFile "w")

unless( port
    printf("ERROR: could not open ADE XL setup raw file: %s\n" outFile)
    return(nil)
)

foreach(varName cadr(vars)
    varObj = axlGetVar(setupDb varName)
    val = axlGetVarValue(varObj)

    fprintf(port "%s=%s\n" varName val)
)

close(port)

cmd = strcat(
    "/usr/bin/python " DTRACE_PY
    " capture-adexl-setup "
    checkpointId " "
    outFile
    " >> " DTRACE_LOG " 2>&1"
)

system(cmd)

printf("DTrace: ADE XL setup captured for %s\n" checkpointId)

t
)
```

)

; =====================================================================
; Optional ADE XL bindkey
; Uncomment or modify as needed for local setup.
; =====================================================================

; hiSetBindKey("adexl" "F5" "dtraceRun()")
