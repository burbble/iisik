from __future__ import annotations

"""Runtime protobuf message classes for the LR2 gRPC contract.

The source of truth is docs/proto/profitability.proto.  This module constructs the
same descriptors with google.protobuf at import time so the repository is runnable
without committing protoc-generated files.
"""

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

PKG = "profitability.v1"


def _field(msg, name, number, field_type, label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL, type_name=None):
    f = msg.field.add()
    f.name = name
    f.number = number
    f.type = field_type
    f.label = label
    if type_name:
        f.type_name = type_name
    return f


def _message(fd, name, fields):
    msg = fd.message_type.add()
    msg.name = name
    for spec in fields:
        _field(msg, *spec)
    return msg


def _service(fd, name, methods):
    service = fd.service.add()
    service.name = name
    for method_name, input_name, output_name in methods:
        m = service.method.add()
        m.name = method_name
        m.input_type = f".{PKG}.{input_name}"
        m.output_type = f".{PKG}.{output_name}"


def _build_file_descriptor():
    fd = descriptor_pb2.FileDescriptorProto()
    fd.name = "profitability.proto"
    fd.package = PKG
    fd.syntax = "proto3"

    T = descriptor_pb2.FieldDescriptorProto
    OPT = T.LABEL_OPTIONAL
    REP = T.LABEL_REPEATED

    _message(fd, "GetCostingContextRequest", [
        ("product_id", 1, T.TYPE_STRING),
        ("period", 2, T.TYPE_STRING),
    ])
    _message(fd, "MaterialNorm", [
        ("material_id", 1, T.TYPE_STRING),
        ("standard_qty", 2, T.TYPE_STRING),
    ])
    _message(fd, "GetCostingContextResponse", [
        ("product_id", 1, T.TYPE_STRING),
        ("materials", 2, T.TYPE_MESSAGE, REP, f".{PKG}.MaterialNorm"),
        ("allocation_base", 3, T.TYPE_STRING),
        ("data_version", 4, T.TYPE_STRING),
    ])

    _message(fd, "GetProductionCostDataRequest", [
        ("product_id", 1, T.TYPE_STRING),
        ("period", 2, T.TYPE_STRING),
    ])
    _message(fd, "GetProductionCostDataResponse", [
        ("produced_qty", 1, T.TYPE_STRING),
        ("material_cost", 2, T.TYPE_STRING),
        ("labor_cost", 3, T.TYPE_STRING),
        ("production_order_ids", 4, T.TYPE_STRING, REP),
        ("data_version", 5, T.TYPE_STRING),
        ("labor_hours", 6, T.TYPE_STRING),
    ])

    _message(fd, "GetOverheadDataRequest", [
        ("period", 1, T.TYPE_STRING),
        ("cost_center_ids", 2, T.TYPE_STRING, REP),
    ])
    _message(fd, "OverheadAmount", [
        ("cost_center_id", 1, T.TYPE_STRING),
        ("amount", 2, T.TYPE_STRING),
    ])
    _message(fd, "GetOverheadDataResponse", [
        ("items", 1, T.TYPE_MESSAGE, REP, f".{PKG}.OverheadAmount"),
        ("correction_amount", 2, T.TYPE_STRING),
        ("data_version", 3, T.TYPE_STRING),
    ])
    _message(fd, "GetSalesDataRequest", [
        ("product_id", 1, T.TYPE_STRING),
        ("period", 2, T.TYPE_STRING),
    ])
    _message(fd, "GetSalesDataResponse", [
        ("sold_qty", 1, T.TYPE_STRING),
        ("revenue", 2, T.TYPE_STRING),
        ("currency", 3, T.TYPE_STRING),
        ("data_version", 4, T.TYPE_STRING),
    ])

    _message(fd, "GetApprovedCostCalculationRequest", [
        ("product_id", 1, T.TYPE_STRING),
        ("period", 2, T.TYPE_STRING),
        ("version", 3, T.TYPE_INT32),
    ])
    _message(fd, "GetApprovedCostCalculationResponse", [
        ("calculation_id", 1, T.TYPE_STRING),
        ("version", 2, T.TYPE_INT32),
        ("unit_cost", 3, T.TYPE_STRING),
        ("total_cost", 4, T.TYPE_STRING),
        ("produced_qty", 5, T.TYPE_STRING),
        ("status", 6, T.TYPE_STRING),
    ])

    _message(fd, "GetProfitabilityDetailRequest", [
        ("product_id", 1, T.TYPE_STRING),
        ("period", 2, T.TYPE_STRING),
    ])
    _message(fd, "GetProfitabilityDetailResponse", [
        ("result_id", 1, T.TYPE_STRING),
        ("revenue", 2, T.TYPE_STRING),
        ("cost_of_sales", 3, T.TYPE_STRING),
        ("profit", 4, T.TYPE_STRING),
        ("margin_percent", 5, T.TYPE_STRING),
        ("calculated_at", 6, T.TYPE_STRING),
    ])

    _service(fd, "MasterDataService", [
        ("GetCostingContext", "GetCostingContextRequest", "GetCostingContextResponse"),
    ])
    _service(fd, "ProductionDataService", [
        ("GetProductionCostData", "GetProductionCostDataRequest", "GetProductionCostDataResponse"),
    ])
    _service(fd, "FinancialDataService", [
        ("GetOverheadData", "GetOverheadDataRequest", "GetOverheadDataResponse"),
        ("GetSalesData", "GetSalesDataRequest", "GetSalesDataResponse"),
    ])
    _service(fd, "CostingService", [
        ("GetApprovedCostCalculation", "GetApprovedCostCalculationRequest", "GetApprovedCostCalculationResponse"),
    ])
    _service(fd, "ProfitabilityService", [
        ("GetProfitabilityDetail", "GetProfitabilityDetailRequest", "GetProfitabilityDetailResponse"),
    ])
    return fd


_pool = descriptor_pool.DescriptorPool()
FILE_DESCRIPTOR = _pool.Add(_build_file_descriptor())


def _cls(name: str):
    return message_factory.GetMessageClass(_pool.FindMessageTypeByName(f"{PKG}.{name}"))


GetCostingContextRequest = _cls("GetCostingContextRequest")
MaterialNorm = _cls("MaterialNorm")
GetCostingContextResponse = _cls("GetCostingContextResponse")
GetProductionCostDataRequest = _cls("GetProductionCostDataRequest")
GetProductionCostDataResponse = _cls("GetProductionCostDataResponse")
GetOverheadDataRequest = _cls("GetOverheadDataRequest")
OverheadAmount = _cls("OverheadAmount")
GetOverheadDataResponse = _cls("GetOverheadDataResponse")
GetSalesDataRequest = _cls("GetSalesDataRequest")
GetSalesDataResponse = _cls("GetSalesDataResponse")
GetApprovedCostCalculationRequest = _cls("GetApprovedCostCalculationRequest")
GetApprovedCostCalculationResponse = _cls("GetApprovedCostCalculationResponse")
GetProfitabilityDetailRequest = _cls("GetProfitabilityDetailRequest")
GetProfitabilityDetailResponse = _cls("GetProfitabilityDetailResponse")

__all__ = [name for name in globals() if name.startswith("Get") or name in {"MaterialNorm", "OverheadAmount", "FILE_DESCRIPTOR"}]
