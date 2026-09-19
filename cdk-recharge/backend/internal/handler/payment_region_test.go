package handler

import (
	"testing"

	"github.com/tuzi/cdk-recharge-system/internal/cardplatform"
)

func TestIssuePrefsWithPaymentCountry(t *testing.T) {
	cases := []struct {
		name     string
		pref     cardplatform.IssueCardPref
		hasPref  bool
		country  string
		wantLen  int
		wantCode string
	}{
		{name: "default keeps old behavior"},
		{name: "region without card preference", country: " cl ", wantLen: 1, wantCode: "CL"},
		{name: "card preference without region", pref: cardplatform.IssueCardPref{Issuer: "one"}, hasPref: true, wantLen: 1},
		{name: "both remain independent", pref: cardplatform.IssueCardPref{Issuer: "one"}, hasPref: true, country: "jp", wantLen: 1, wantCode: "JP"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := issuePrefsWithPaymentCountry(tc.pref, tc.hasPref, tc.country)
			if len(got) != tc.wantLen {
				t.Fatalf("prefs = %+v, want len %d", got, tc.wantLen)
			}
			if tc.wantLen > 0 {
				if got[0].PaymentCountry != tc.wantCode || got[0].Issuer != tc.pref.Issuer {
					t.Fatalf("prefs = %+v, want country %q and issuer %q", got, tc.wantCode, tc.pref.Issuer)
				}
			}
		})
	}
}
