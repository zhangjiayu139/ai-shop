package cardplatform

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGetPlansUsesUpstreamPaymentRegions(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/openapi/v1/gpt-direct/plans" {
			t.Errorf("path = %q", r.URL.Path)
		}
		_, _ = w.Write([]byte(`{"code":0,"data":{"version":9,"plans":{},"payment_regions":[{"country":"CL","currency":"CLP"},{"country":"JP","currency":"JPY"}]}}`))
	}))
	defer server.Close()

	got, err := New(Config{SiteBase: server.URL, APIKey: "test-key"}).GetPlans(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if len(got.PaymentRegions) != 2 || got.PaymentRegions[0].Country != "CL" || got.PaymentRegions[0].Currency != "CLP" || got.PaymentRegions[1].Country != "JP" {
		t.Fatalf("payment regions = %+v", got.PaymentRegions)
	}
}

func TestIssueCDKsSendsOnlySelectedCountry(t *testing.T) {
	var received map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/openapi/v1/gpt-direct/cdks" {
			t.Errorf("path = %q", r.URL.Path)
		}
		received = nil
		if err := json.NewDecoder(r.Body).Decode(&received); err != nil {
			t.Errorf("decode request: %v", err)
		}
		_, _ = w.Write([]byte(`{"code":0,"data":{"requested":1,"issued":[]}}`))
	}))
	defer server.Close()
	client := New(Config{SiteBase: server.URL, APIKey: "test-key"})

	if _, err := client.IssueCDKs(context.Background(), "plus", 1, "test-idem", IssueCardPref{PaymentCountry: " cl "}); err != nil {
		t.Fatal(err)
	}
	if received["payment_country"] != "CL" {
		t.Fatalf("selected country not forwarded: %+v", received)
	}
	if _, present := received["currency"]; present {
		t.Fatalf("currency must be decided by upstream: %+v", received)
	}
	if _, err := client.IssueCDKs(context.Background(), "plus", 1, "test-default"); err != nil {
		t.Fatal(err)
	}
	if _, present := received["payment_country"]; present {
		t.Fatalf("default issue must omit payment country: %+v", received)
	}
}
