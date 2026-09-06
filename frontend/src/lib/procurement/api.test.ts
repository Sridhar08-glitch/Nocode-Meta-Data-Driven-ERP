import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({
  apiGet: vi.fn(() => Promise.resolve({})),
  apiSend: vi.fn(() => Promise.resolve({})),
}));
import { apiSend } from "@/lib/api/request";
import { procurementApi } from "./api";

beforeEach(() => {
  vi.mocked(apiSend).mockClear();
});

describe("procurementApi", () => {
  it("hits the native procurement lifecycle endpoints", () => {
    procurementApi.setup();
    procurementApi.createDocument("rfq", { vendor: "v1" });
    procurementApi.approveDocument("purchase_order", "po1");
    procurementApi.postGoodsReceipt("gr1");
    procurementApi.postVendorBill("vb1");

    expect(apiSend).toHaveBeenCalledWith("/api/v1/procurement/setup/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/procurement/rfq/", "POST", { vendor: "v1" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/procurement/purchase_order/po1/approve/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/procurement/goods-receipts/gr1/post/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/procurement/vendor-bills/vb1/post/", "POST");
  });
});
