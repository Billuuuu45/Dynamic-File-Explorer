from fastapi import APIRouter, HTTPException, Query
from services.file_service import file_service

router = APIRouter()

@router.get("/folders")
async def list_folders(path: str = Query("", description="Folder path relative to root"),
                       search: str = Query(None, description="Optional search term")):
    """Returns all folders under the given path, optionally filtered by search."""
    try:
        return await file_service.get_folders(path, search)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Directory not found")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/files")
async def list_files(path: str = Query("", description="Folder path relative to root"),
                     search: str = Query(None, description="Optional search term")):
    """Returns files inside the selected directory, optionally filtered by search."""
    try:
        return await file_service.get_files(path, search)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Directory not found")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metadata")
async def get_metadata(path: str = Query(..., description="File path relative to root")):
    """Returns metadata of the selected file."""
    try:
        return await file_service.get_file_metadata(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/read")
async def read_file(path: str = Query(..., description="File path relative to root")):
    """Returns the contents of the selected file."""
    try:
        return await file_service.read_file_content(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/connectors")
async def get_connectors():
    """Returns dynamic data for the MCP connectors dashboard."""
    return [
        {
            "id": "s3",
            "icon": "S3",
            "title": "Amazon S3 — plant archive",
            "subtitle": "s3://xyl-plant-archive/coimbatore-u2/",
            "description": "Scanned batch records, P&IDs, vendor manuals",
            "mcp_server": "mcp-server-s3 v1.4.2",
            "objects": "18,432",
            "status": "CONNECTED",
            "protocol": "OBJECT STORAGE",
            "time": "2 min"
        },
        {
            "id": "smb",
            "icon": "SMB",
            "title": "Windows file server — ENG01",
            "subtitle": "\\\\eng01.plant.local\\Engineering$",
            "description": "Drawings, SOPs, calibration certificates",
            "mcp_server": "mcp-server-fileshare v0.9.7",
            "objects": "9,714",
            "status": "CONNECTED",
            "protocol": "SMB / CIFS SHARE",
            "time": "4 min"
        },
        {
            "id": "od",
            "icon": "OD",
            "title": "OneDrive / SharePoint — Quality",
            "subtitle": "sites/quality-assurance/Shared Documents",
            "description": "NCRs, audit packs, CAPA records",
            "mcp_server": "mcp-server-msgraph v2.1.0",
            "objects": "6,120",
            "status": "CONNECTED",
            "protocol": "MICROSOFT GRAPH",
            "time": "1 min"
        },
        {
            "id": "pi",
            "icon": "PI",
            "title": "SCADA historian — OSIsoft PI",
            "subtitle": "pi://hist01.plant.local/ · 4,812 tags",
            "description": "1s-1min tag streams from Lines 1-4",
            "mcp_server": "mcp-server-pi v1.2.0",
            "objects": "4,812",
            "status": "CONNECTED",
            "protocol": "TIME-SERIES TAGS",
            "time": "live"
        },
        {
            "id": "sap",
            "icon": "SAP",
            "title": "SAP S/4HANA — PM / QM / MM",
            "subtitle": "sap://prd100/ · 38 extractors",
            "description": "Work orders, batches, notifications, BOM",
            "mcp_server": "mcp-server-sap v1.0.4",
            "objects": "38",
            "status": "CONNECTED",
            "protocol": "ODATA + RFC",
            "time": "15 min"
        },
        {
            "id": "sql",
            "icon": "SQL",
            "title": "MSSQL — MES & SPC database",
            "subtitle": "mssql://mes-db01/MES_PROD · 21 tables",
            "description": "Downtime, OEE, SPC samples, genealogy",
            "mcp_server": "mcp-server-mssql v1.6.1",
            "objects": "21",
            "status": "CONNECTED",
            "protocol": "RELATIONAL",
            "time": "5 min"
        }
    ]
