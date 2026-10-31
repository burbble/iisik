from __future__ import annotations

import grpc

from app.contracts import profitability_pb as pb


def _serializer(message):
    return message.SerializeToString()


class MasterDataStub:
    def __init__(self, channel: grpc.Channel):
        self.LookupExternalMapping = channel.unary_unary(
            "/profitability.v1.MasterDataService/LookupExternalMapping",
            request_serializer=_serializer,
            response_deserializer=pb.LookupExternalMappingResponse.FromString,
        )
        self.GetCostingContext = channel.unary_unary(
            "/profitability.v1.MasterDataService/GetCostingContext",
            request_serializer=_serializer,
            response_deserializer=pb.GetCostingContextResponse.FromString,
        )


class ProductionDataStub:
    def __init__(self, channel: grpc.Channel):
        self.GetProductionCostData = channel.unary_unary(
            "/profitability.v1.ProductionDataService/GetProductionCostData",
            request_serializer=_serializer,
            response_deserializer=pb.GetProductionCostDataResponse.FromString,
        )


class FinancialDataStub:
    def __init__(self, channel: grpc.Channel):
        self.GetOverheadData = channel.unary_unary(
            "/profitability.v1.FinancialDataService/GetOverheadData",
            request_serializer=_serializer,
            response_deserializer=pb.GetOverheadDataResponse.FromString,
        )
        self.GetSalesData = channel.unary_unary(
            "/profitability.v1.FinancialDataService/GetSalesData",
            request_serializer=_serializer,
            response_deserializer=pb.GetSalesDataResponse.FromString,
        )


class CostingStub:
    def __init__(self, channel: grpc.Channel):
        self.GetApprovedCostCalculation = channel.unary_unary(
            "/profitability.v1.CostingService/GetApprovedCostCalculation",
            request_serializer=_serializer,
            response_deserializer=pb.GetApprovedCostCalculationResponse.FromString,
        )


class ProfitabilityStub:
    def __init__(self, channel: grpc.Channel):
        self.GetProfitabilityDetail = channel.unary_unary(
            "/profitability.v1.ProfitabilityService/GetProfitabilityDetail",
            request_serializer=_serializer,
            response_deserializer=pb.GetProfitabilityDetailResponse.FromString,
        )


def add_master_data_handler(server: grpc.Server, fn, mapping_fn):
    handler = grpc.unary_unary_rpc_method_handler(
        fn,
        request_deserializer=pb.GetCostingContextRequest.FromString,
        response_serializer=_serializer,
    )
    server.add_generic_rpc_handlers(
        (
            grpc.method_handlers_generic_handler(
                "profitability.v1.MasterDataService",
                {
                    "GetCostingContext": handler,
                    "LookupExternalMapping": grpc.unary_unary_rpc_method_handler(
                        mapping_fn,
                        request_deserializer=pb.LookupExternalMappingRequest.FromString,
                        response_serializer=_serializer,
                    ),
                },
            ),
        )
    )


def add_production_handler(server: grpc.Server, fn):
    handler = grpc.unary_unary_rpc_method_handler(
        fn,
        request_deserializer=pb.GetProductionCostDataRequest.FromString,
        response_serializer=_serializer,
    )
    server.add_generic_rpc_handlers(
        (
            grpc.method_handlers_generic_handler(
                "profitability.v1.ProductionDataService",
                {"GetProductionCostData": handler},
            ),
        )
    )


def add_financial_handler(server: grpc.Server, overhead_fn, sales_fn):
    handlers = {
        "GetOverheadData": grpc.unary_unary_rpc_method_handler(
            overhead_fn,
            request_deserializer=pb.GetOverheadDataRequest.FromString,
            response_serializer=_serializer,
        ),
        "GetSalesData": grpc.unary_unary_rpc_method_handler(
            sales_fn,
            request_deserializer=pb.GetSalesDataRequest.FromString,
            response_serializer=_serializer,
        ),
    }
    server.add_generic_rpc_handlers(
        (
            grpc.method_handlers_generic_handler(
                "profitability.v1.FinancialDataService", handlers
            ),
        )
    )


def add_costing_handler(server: grpc.Server, fn):
    handler = grpc.unary_unary_rpc_method_handler(
        fn,
        request_deserializer=pb.GetApprovedCostCalculationRequest.FromString,
        response_serializer=_serializer,
    )
    server.add_generic_rpc_handlers(
        (
            grpc.method_handlers_generic_handler(
                "profitability.v1.CostingService",
                {"GetApprovedCostCalculation": handler},
            ),
        )
    )


def add_profitability_handler(server: grpc.Server, fn):
    handler = grpc.unary_unary_rpc_method_handler(
        fn,
        request_deserializer=pb.GetProfitabilityDetailRequest.FromString,
        response_serializer=_serializer,
    )
    server.add_generic_rpc_handlers(
        (
            grpc.method_handlers_generic_handler(
                "profitability.v1.ProfitabilityService",
                {"GetProfitabilityDetail": handler},
            ),
        )
    )
