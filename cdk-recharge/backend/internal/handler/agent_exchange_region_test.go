package handler

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/tuzi/cdk-recharge-system/internal/db"
)

func TestAgentExchangePreservesPaymentRegion(t *testing.T) {
	str := func(s string) *string { return &s }
	for _, tc := range []struct {
		name, listJSON, wantCountry string
		stored, issuedCountry       *string
		listStatus, wantStatus      int
		wantLookup, hasPref         bool
	}{
		{name: "cached Chile", stored: str(" cl "), wantCountry: "CL", wantStatus: 200},
		{name: "Chile with card preference", stored: str("CL"), wantCountry: "CL", wantStatus: 200, hasPref: true},
		{name: "cached default", stored: str(""), wantStatus: 200},
		{name: "lookup Japan", listJSON: `{"list":[{"id":1,"payment_country":" jp "}]}`, wantCountry: "JP", wantStatus: 200, wantLookup: true},
		{name: "lookup explicit default", listJSON: `{"list":[{"id":1,"payment_country":""}]}`, wantStatus: 200, wantLookup: true},
		{name: "missing region", listJSON: `{"list":[{"id":1}]}`, wantStatus: 503, wantLookup: true},
		{name: "null region", listJSON: `{"list":[{"id":1,"payment_country":null}]}`, wantStatus: 503, wantLookup: true},
		{name: "wrong code", listJSON: `{"list":[{"id":11,"payment_country":"CL"}]}`, wantStatus: 503, wantLookup: true},
		{name: "upstream unavailable", listStatus: 503, wantStatus: 503, wantLookup: true},
		{name: "matching issued country", stored: str("CL"), issuedCountry: str(" cl "), wantCountry: "CL", wantStatus: 200},
		{name: "mismatched issued country", stored: str("CL"), issuedCountry: str("JP"), wantCountry: "CL", wantStatus: 409},
		{name: "unexpected issued default", stored: str("CL"), issuedCountry: str(""), wantCountry: "CL", wantStatus: 409},
	} {
		t.Run(tc.name, func(t *testing.T) {
			swapRateMu.Lock()
			oldHits := swapRateHits
			swapRateHits = make(map[string][]time.Time)
			swapRateMu.Unlock()
			t.Cleanup(func() {
				swapRateMu.Lock()
				swapRateHits = oldHits
				swapRateMu.Unlock()
			})
			t.Setenv("DB_PATH", filepath.Join(t.TempDir(), "fixture.db"))
			oldDB := db.DB
			if err := db.Init(nil); err != nil {
				t.Fatal(err)
			}
			conn := db.DB
			t.Cleanup(func() { conn.Close(); db.DB = oldDB })
			if _, err := conn.Exec(`DELETE FROM card_selection_rules`); err != nil {
				t.Fatal(err)
			}
			if tc.hasPref {
				if _, err := conn.Exec(`INSERT INTO card_selection_rules(sort_order,plan_key,display_name,channel,enabled) VALUES(1,'TEST-PRODUCT','Fixture product','one',1)`); err != nil {
					t.Fatal(err)
				}
			}
			if err := setAgentSwapPassword("fixture-password"); err != nil {
				t.Fatal(err)
			}
			if _, err := conn.Exec(`INSERT INTO cardplatform_cdk_codes(upstream_id,code,plan,payment_country) VALUES(1,'TEST-OLD-CDK-001','plus',?)`, tc.stored); err != nil {
				t.Fatal(err)
			}
			issued, disabled, lookedUp := 0, 0, false
			upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.Header().Set("Content-Type", "application/json")
				switch {
				case r.URL.Path == "/openapi/v1/gpt-direct/cdk-orders":
					w.Write([]byte(`{"code":0,"data":{"list":[{"id":10,"status":"failed_precharge","final_amount_minor":0}],"total":1}}`))
				case r.URL.Path == "/openapi/v1/gpt-direct/cdk-orders/10":
					w.Write([]byte(`{"code":0,"data":{"order":{"status":"failed_precharge","final_amount_minor":0},"events":[]}}`))
				case r.URL.Path == "/openapi/v1/gpt-direct/cdks" && r.Method == "GET":
					lookedUp = true
					if r.URL.Query().Get("q") != "1" {
						t.Error("region lookup must use original upstream ID")
					}
					if tc.listStatus != 0 {
						w.WriteHeader(tc.listStatus)
						return
					}
					w.Write([]byte(`{"code":0,"data":` + tc.listJSON + `}`))
				case r.URL.Path == "/openapi/v1/gpt-direct/cdks" && r.Method == "POST":
					issued++
					var body map[string]any
					if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
						t.Error(err)
					}
					got, _ := body["payment_country"].(string)
					if got != tc.wantCountry || body["plan"] != "plus" || body["count"] != float64(1) {
						t.Errorf("wrong replacement parameters: %v", body)
					}
					if tc.hasPref && (body["preferred_issuer"] != "one" || body["preferred_segment_key"] != "TEST-PRODUCT") {
						t.Errorf("card preference lost: %v", body)
					}
					item := map[string]any{"id": 2, "code": "TEST-NEW-CDK-002", "fee_amount_minor": 15}
					if tc.issuedCountry != nil {
						item["payment_country"] = *tc.issuedCountry
					}
					json.NewEncoder(w).Encode(map[string]any{"code": 0, "data": map[string]any{"issued": []any{item}}})
				case r.URL.Path == "/openapi/v1/gpt-direct/cdks/1/disable":
					disabled++
					w.Write([]byte(`{"code":0,"data":{}}`))
				default:
					t.Errorf("unexpected upstream request %s %s", r.Method, r.URL.Path)
					w.WriteHeader(404)
				}
			}))
			defer upstream.Close()
			if err := db.SetSetting("card_api_base", upstream.URL); err != nil {
				t.Fatal(err)
			}
			if err := db.SetSetting("card_api_key", "fixture-key"); err != nil {
				t.Fatal(err)
			}
			gin.SetMode(gin.TestMode)
			router := gin.New()
			router.POST("/exchange", PublicAgentCDKExchange)
			req := httptest.NewRequest("POST", "/exchange", strings.NewReader(`{"password":"fixture-password","code":"TEST-OLD-CDK-001"}`))
			req.Header.Set("Content-Type", "application/json")
			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)
			if w.Code != tc.wantStatus || lookedUp != tc.wantLookup {
				t.Errorf("status=%d want=%d lookup=%v want=%v response=%s", w.Code, tc.wantStatus, lookedUp, tc.wantLookup, w.Body.String())
			}
			wantIssued, wantDisabled := 0, 0
			if tc.wantStatus == 200 || tc.wantStatus == 409 {
				wantIssued = 1
				wantCached := tc.wantCountry
				if tc.issuedCountry != nil {
					wantCached = strings.ToUpper(strings.TrimSpace(*tc.issuedCountry))
				}
				var country sql.NullString
				if err := conn.QueryRow(`SELECT payment_country FROM cardplatform_cdk_codes WHERE upstream_id=2`).Scan(&country); err != nil || !country.Valid || country.String != wantCached {
					t.Errorf("new code region=%+v want=%q err=%v", country, wantCached, err)
				}
			}
			if tc.wantStatus == 200 {
				wantDisabled = 1
				var response map[string]any
				if err := json.Unmarshal(w.Body.Bytes(), &response); err != nil || response["payment_country"] != tc.wantCountry {
					t.Errorf("missing response region: %s", w.Body.String())
				}
			}
			if issued != wantIssued || disabled != wantDisabled {
				t.Errorf("issue=%d disable=%d want=%d/%d", issued, disabled, wantIssued, wantDisabled)
			}
			var oldCountry sql.NullString
			if err := conn.QueryRow(`SELECT payment_country FROM cardplatform_cdk_codes WHERE upstream_id=1`).Scan(&oldCountry); err != nil {
				t.Fatal(err)
			}
			if tc.stored == nil && (oldCountry.Valid != (tc.wantStatus == 200) || oldCountry.Valid && oldCountry.String != tc.wantCountry) {
				t.Errorf("unknown region was not safely refreshed: %+v", oldCountry)
			}
			if db.AgentCDKAlreadyExchanged(db.HashCDKCode("TEST-OLD-CDK-001")) != (wantIssued == 1) {
				t.Error("exchange record does not match issuance outcome")
			}
			if tc.wantStatus == 409 {
				if !strings.Contains(w.Body.String(), "payment_region_mismatch") || strings.Contains(w.Body.String(), "TEST-NEW-CDK-002") {
					t.Errorf("mismatched code must await admin handling: %s", w.Body.String())
				}
				var state string
				if err := conn.QueryRow(`SELECT order_status FROM agent_cdk_exchanges WHERE new_upstream_id=2`).Scan(&state); err != nil || state != "region_mismatch" {
					t.Errorf("missing mismatch record: %s %v", state, err)
				}
				retry := httptest.NewRequest("POST", "/exchange", strings.NewReader(`{"password":"fixture-password","code":"TEST-OLD-CDK-001"}`))
				retry.Header.Set("Content-Type", "application/json")
				result := httptest.NewRecorder()
				router.ServeHTTP(result, retry)
				if result.Code != 409 || issued != 1 || disabled != 0 {
					t.Errorf("retry must not issue again or disable original: status=%d issue=%d disable=%d", result.Code, issued, disabled)
				}
			}
		})
	}
}
