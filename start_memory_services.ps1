param(
    [int]$PostgresHostPort = 5432,
    [int]$QdrantHostPort = 6333,
    [switch]$ForceRecreate
)

$ErrorActionPreference = "Stop"

$postgresContainer = "ai-cs-postgres"
$qdrantContainer = "ai-cs-qdrant"
$postgresImage = "postgres:16"
$qdrantImage = "qdrant/qdrant"
$postgresPort = $PostgresHostPort
$qdrantPort = $QdrantHostPort

function Test-DockerInstalled {
    $null = Get-Command docker -ErrorAction Stop
}

function Get-PortUsageMessage {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    if (-not $connections) {
        return ""
    }

    $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    $processNames = foreach ($pid in $pids) {
        $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($process) {
            "$($process.ProcessName)($pid)"
        }
        else {
            "PID=$pid"
        }
    }

    $owners = ($processNames | Where-Object { $_ }) -join ", "
    if (-not $owners) {
        $owners = "未知进程"
    }

    return "Host port $Port is already in use by: $owners"
}

function Normalize-Text {
    param(
        [AllowNull()]
        [object]$Value
    )

    if ($null -eq $Value) {
        return ""
    }

    return ([string]$Value).Trim()
}

function Invoke-DockerCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$FailureMessage,
        [switch]$AllowFailure
    )

    $stdoutFile = [System.IO.Path]::GetTempFileName()
    $stderrFile = [System.IO.Path]::GetTempFileName()

    try {
        $process = Start-Process `
            -FilePath "docker" `
            -ArgumentList $Arguments `
            -NoNewWindow `
            -Wait `
            -PassThru `
            -RedirectStandardOutput $stdoutFile `
            -RedirectStandardError $stderrFile

        $stdout = ""
        $stderr = ""
        if (Test-Path $stdoutFile) {
            $stdout = (Get-Content $stdoutFile -Raw -ErrorAction SilentlyContinue)
        }
        if (Test-Path $stderrFile) {
            $stderr = (Get-Content $stderrFile -Raw -ErrorAction SilentlyContinue)
        }

        $stdoutText = Normalize-Text $stdout
        $stderrText = Normalize-Text $stderr

        if ($process.ExitCode -ne 0 -and -not $AllowFailure) {
            if ($stderrText -match "listen tcp 0\.0\.0\.0:(\d+): bind") {
                $portMessage = Get-PortUsageMessage -Port ([int]$matches[1])
                if ($portMessage) {
                    throw (Normalize-Text "$FailureMessage`n$portMessage`nYou can stop the conflicting service, or change the host port and update config.yaml.")
                }
            }
            if ($stderrText) {
                throw (Normalize-Text "$FailureMessage`n$stderrText")
            }
            throw $FailureMessage
        }

        return @{
            ExitCode = $process.ExitCode
            StdOut = $stdoutText
            StdErr = $stderrText
        }
    }
    finally {
        Remove-Item -LiteralPath $stdoutFile, $stderrFile -ErrorAction SilentlyContinue
    }
}

function Assert-DockerDaemonAvailable {
    $result = Invoke-DockerCommand `
        -Arguments @("info", "--format", "{{.ServerVersion}}") `
        -FailureMessage "Failed to query Docker daemon." `
        -AllowFailure

    if ($result.ExitCode -ne 0) {
        throw @"
Docker daemon is not running or is not reachable.
Please start Docker Desktop (or another Docker daemon) and then rerun:
  .\start_memory_services.ps1
"@
    }
}

function Get-ContainerIdByName {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $result = Invoke-DockerCommand `
        -Arguments @("ps", "-aq", "-f", "name=^${Name}$") `
        -FailureMessage "Failed to query container '$Name'."

    return $result.StdOut
}

function Remove-ContainerIfExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $containerId = Get-ContainerIdByName -Name $Name
    if (-not $containerId) {
        return
    }

    Write-Host "Removing existing container: $Name"
    Invoke-DockerCommand `
        -Arguments @("rm", "-f", $containerId) `
        -FailureMessage "Failed to remove container '$Name'." | Out-Null
}

function Ensure-ContainerRunning {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$Image,
        [Parameter(Mandatory = $true)]
        [string[]]$RunArgs
    )

    if ($ForceRecreate) {
        Remove-ContainerIfExists -Name $Name
    }

    $containerId = Get-ContainerIdByName -Name $Name
    if (-not $containerId) {
        Write-Host "Creating container: $Name"
        $dockerRunArgs = @("run") + $RunArgs
        Invoke-DockerCommand `
            -Arguments $dockerRunArgs `
            -FailureMessage "Failed to create container '$Name' from image '$Image'." | Out-Null
        return
    }

    $inspectResult = Invoke-DockerCommand `
        -Arguments @("inspect", "-f", "{{.State.Running}}", $containerId) `
        -FailureMessage "Failed to inspect container '$Name'."
    $isRunning = $inspectResult.StdOut

    if ($isRunning -eq "true") {
        Write-Host "Container already running: $Name"
        return
    }

    Write-Host "Starting existing container: $Name"
    Invoke-DockerCommand `
        -Arguments @("start", $containerId) `
        -FailureMessage "Failed to start container '$Name'." | Out-Null
}

function Wait-ForPort {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port,
        [Parameter(Mandatory = $true)]
        [string]$ServiceName,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $result = Test-NetConnection -ComputerName localhost -Port $Port -WarningAction SilentlyContinue
        if ($null -ne $result -and $result.TcpTestSucceeded) {
            Write-Host "$ServiceName is ready on port $Port"
            return
        }
        Start-Sleep -Seconds 2
    }

    throw "$ServiceName did not become ready on port $Port within $TimeoutSeconds seconds."
}

try {
    Test-DockerInstalled
    Assert-DockerDaemonAvailable

    Ensure-ContainerRunning -Name $postgresContainer -Image $postgresImage -RunArgs @(
        "--name", $postgresContainer,
        "-e", "POSTGRES_PASSWORD=postgres",
        "-e", "POSTGRES_DB=ai_customer_service",
        "-p", "${postgresPort}:5432",
        "-d",
        $postgresImage
    )

    Ensure-ContainerRunning -Name $qdrantContainer -Image $qdrantImage -RunArgs @(
        "--name", $qdrantContainer,
        "-p", "${qdrantPort}:6333",
        "-d",
        $qdrantImage
    )

    Wait-ForPort -Port $postgresPort -ServiceName "Postgres"
    Wait-ForPort -Port $qdrantPort -ServiceName "Qdrant"

    Write-Host ""
    Write-Host "All memory services are up."
    Write-Host "Postgres: postgresql://postgres:postgres@localhost:${postgresPort}/ai_customer_service"
    Write-Host "Qdrant:   http://localhost:${qdrantPort}"
}
catch {
    Write-Host ""
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
