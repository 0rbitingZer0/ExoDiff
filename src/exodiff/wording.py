STAT = ("Gap in error bars = difference ÷ √(σ₁² + σ₂²), where σ₁ and σ₂ are the two values' uncertainties. "
        "Rounding is allowed for, and a gap of more than 2 is a finding. The combined uncertainty is approximate: it "
        "assumes independent errors, uses each value's ± on the side facing the other value, and averages uneven ± ranges "
        "for values computed from several inputs. This is a screening rule, not a p-value.")

NEW = {
"general/finding": ("", "Worth a closer look. These values don't agree under ExoDiff's stated check, and none of the explanations tested so far accounts for the gap. This is not proof that either source is wrong.", ""),
"general/note": ("", "Shown for context, not counted. A note means one of four things: the gap is below ExoDiff's threshold; the gap can't be judged (no usable uncertainty); a value is a limit, an estimate or labelled theoretical by its source, so it isn't compared as a measurement; or the gap matches an explanation ExoDiff tests for (for example another paper or a unit convention), which may explain it but isn't confirmed.", ""),
"general/uncertainty": ("", "ExoDiff compares published uncertainty ranges where available. Its threshold is **a screening rule, not a verdict** that two scientific results disagree. Uncertainty ranges are estimates at the paper's stated confidence level, where provided, rather than hard bounds. They may omit some sources of error. Limits such as 'at most' and 'at least' are handled separately.", STAT),
"general/no-uncertainty": ("", "If at least one source gives no usable uncertainty, ExoDiff can't judge how much the difference matters. **A missing uncertainty doesn't mean the value is wrong.**", "Usable = a parseable, non-zero uncertainty on both sides. Limits follow their own rule."),
"general/precision": ("", "Numbers are shown with the digits stored in the catalogue. Those digits belong to the catalogue; they don't reveal how precisely the original measurement was made.", ""),

"A/A1": ("One value in an archive row, on its own.",
         "Sizes, masses, orbit times, distances, densities and size ratios can't be zero or negative, so this value is invalid for its field as stored. This flags the stored field, not the paper. A typing slip, a placeholder value or an import problem could all cause it.",
         "Columns checked: pl_rade, pl_radj, pl_bmasse, pl_bmassj, pl_masse, pl_massj, pl_msinie, pl_msinij, pl_orbper, pl_orbsmax, pl_dens, pl_ratror, pl_ratdor, st_rad, st_mass, sy_dist (NASA PS table)."),
"A/A2": ("One number in a paper's row: how stretched the orbit is.",
         "This number runs from 0 (a circle) to just under 1 (a very long oval) for a planet going round its star. A value outside that range is invalid for the field as stored. One possible cause: a related fitted quantity that can be negative was stored in this column.",
         "Eccentricity, 0 ≤ e < 1 for a bound orbit. Fits often use √e·cos ω or √e·sin ω, which can be negative; those are not eccentricity."),
"A/A3": ("The uncertainty stored next to a number.",
         "A value written 10 +2 −1 means the estimate is 10, likely between about 9 and 12. NASA's archive stores the upper part as positive and the lower part as negative. Here the stored signs don't follow the archive's convention. The flag is about how the row is stored, not about the paper.",
         "Archive convention: err1 ≥ 0, err2 ≤ 0. Checked on the raw stored fields, not on how a web page displays them."),
"A/A4": ("A number marked as a limit that also has an uncertainty on both sides.",
         "A limit says 'at most' (upper limit) or 'at least' (lower limit). An uncertainty on both sides next to it is unusual but some papers print both, so this is shown as a note to check against the paper.",
         "NASA limit flag: +1 = upper limit, −1 = lower limit, 0 = measurement."),
"A/A5": ("The same number stored twice by NASA: once in Earth units, once in Jupiter units.",
         "Jupiter is 11.2 Earths wide and 318 Earths heavy, so one copy should convert into the other, allowing for rounding. Here they don't, which suggests the two stored copies are inconsistent. It doesn't by itself say the paper's value is wrong or which copy is out of date.",
         "Factors 11.209 (radius) and 317.83 (mass), IAU 2015 nominal values. Allowance = rounding of the digits each copy shows (from NASA's text columns when available) + 0.11% for radius (Earth equatorial vs mean) + 0.1% for mass (conversion factors in use range 317.8–317.9). The two allowances are ExoDiff's project tolerances, not IAU uncertainties."),
"A/A5m": ("The same radius stored in Earth and in Jupiter units.",
          "The two copies are about 2% apart, which matches converting with average sizes instead of equator widths (for both Jupiter and Earth). The standard (IAU) conversion uses equator widths; average sizes are a plausible explanation when the paper used them. Shown as a note when the ratio matches within the stated tolerance.",
          "(71,492 / 6,378.1) ÷ (69,911 / 6,371.0) ≈ 1.0215; matched within rounding."),
"A/A5r": ("The same number stored in Earth and in Jupiter units.",
          "The Earth copy is compatible with the Jupiter value rounded to fewer digits (like writing 4,000 for 3,814). A compatibility test only: the stored digits can't prove how many digits the paper meant.",
          "Compared at the Earth copy's own significant figures, from NASA's text column when available."),
"A/A7": ("Several rows in NASA's archive from the same paper, for the same planet.",
         "The values differ between these rows. They may be different solutions the paper gives (for example from different data or assumptions) or separate imports; it isn't evidence that the paper is inconsistent.",
         "Same planet and reference; differing radius, mass, orbit time, orbit size or eccentricity; star values that also differ are listed."),
"A/A8": ("The star's distance vs the distance its parallax implies, in the same archive row.",
         "A star's parallax (the tiny yearly shift in its position) sets its distance. Here the row's distance and the distance its parallax implies are **5% or more apart and more than 2 error bars apart**, so the archive row is internally inconsistent. ExoDiff doesn't say which number is right.",
         "Default rows only; sy_dist vs 1000 / (sy_plx + 0.029 mas) when sy_refname is TICv8 (TIC v8 distances apply the Gaia DR2 parallax zero-point of −0.029 mas: Bailer-Jones et al. 2018, AJ 156, 58, §2.1; Lindegren et al. 2018, A&A 616, A2), 1000 / sy_plx otherwise; parallax error under 10%. The system parameters can combine sources, e.g. a Hipparcos parallax with a catalogue distance. The source cited is sy_refname."),
"A/A8n": ("The star's distance vs the distance its parallax implies, in the same archive row.",
          "The row's distance and the distance its parallax implies disagree, and NASA's own note on this star says the catalogue distance may be wrong, so it is shown as a note.",
          "Same rule as A8; the note is NASA's System Overview note on the star, citing the same reference as the row's system parameters."),

"card/radius": ("A planet's size as listed vs the size from its own row's other numbers.",
                "As a planet crosses its star it blocks some light. From the dip's depth and shape, astronomers estimate the planet-to-star size ratio; multiplying that ratio by the star's size gives the planet's size. If the listed size doesn't match, the row's values don't combine consistently. That doesn't say which one is off.",
                "Rp = (Rp/R*) × R* × 109.076 Earth radii per solar radius. For a small dark planet and simple geometry the dip depth is approximately (Rp/R*)²; fits also account for limb darkening and light from nearby stars. Columns pl_rade, pl_ratror, st_rad."),
"card/density": ("A planet's density as listed vs the density from its listed mass and size.",
                 "Density is mass divided by volume (water is 1 g/cm³, Earth about 5.5). Volume grows with size cubed, so a small difference in size makes a bigger one in density. If the listed density doesn't follow from the listed mass and size, the row's values don't combine consistently.",
                 "ρ = 5.495 × M(Earths) ÷ R(Earths)³ g/cm³ for a sphere; 5.495 is ExoDiff's adopted conversion with the IAU nominal equatorial Earth radius (5.51 would use Earth's mean radius). Skipped when the mass is a minimum mass, when density, mass or radius is a limit, or when an input has no uncertainty. The listed density's own uncertainty is combined with the uncertainty propagated from mass and radius, all treated as independent (covariance ignored)."),
"card/kepler": ("A planet's orbit size as listed vs the orbit size from its own orbit time and its star's mass.",
                "Gravity ties a planet's distance to how long it takes to go round: farther out, the star's pull is weaker, the planet moves more slowly along a longer path, and a lap takes longer. So once you know the star's mass, the lap time fixes the distance. If the listed orbit size doesn't fit, the row's values don't combine consistently, or they come from different places.",
                "Kepler's third law: a³ = G(M* + Mp)P²/4π². 1 au = the Earth–Sun distance. The planet's mass is added when the row gives one, true or minimum mass (a minimum mass can understate it); a listed planet mass up to about 3 Jupiter masses per solar mass of star changes a by under 0.1%, and its uncertainty isn't propagated. Skipped for planets found by microlensing or direct imaging (the column then holds a projected separation, not an orbit size) and for planets orbiting two stars."),
"card/a_over_rstar": ("The distance to the star counted in star sizes vs orbit size ÷ star size.",
                      "Some papers give the planet's distance in units of the star's own size. For a circular orbit, that should equal the orbit size divided by the star's size.",
                      "NASA's pl_ratdor is the distance at mid-transit ÷ R*, equal to a/R* only for a circular orbit, so this check runs only when the row's eccentricity is 0 (often a value the paper fixed in its fit, an assumption rather than a measurement). a/R* = a(au) × 215.032 ÷ R*(solar radii)."),
"B/B-doc": ("A row whose values don't combine consistently.",
            "NASA has written a note on this planet and paper about the same kind of value. The note may be relevant; its text is shown.",
            "NASA overview-page note matched by paper (ADS bibcode) and topic."),
"B/B-meanR": ("A planet's size or density as listed vs what its own row implies.",
              "The gap matches converting with average sizes instead of equator widths (about 2% in size, 7% in density, since density uses size cubed), within the stated tolerance. A possible convention explanation.",
              "Ratio within 0.5% of 1.0215 or 1.0226 (density: those cubed)."),
"B/B-lit": ("A planet's orbit size vs the orbit size from its orbit time and star mass.",
            "This paper says it took the orbit size from older papers while working out a new star mass itself. Combined, those values don't satisfy Kepler's law. That reflects the paper's stated choices rather than a copying error.",
            "Stassun et al. 2017, §2.7: 'For the non-transiting planets, we use the values of a from the literature.' Applied to that paper's non-transiting rows only."),
"B/B-transit": ("A planet's orbit size vs the orbit size from its orbit time and star mass.",
                "This orbit size appears to come from the transit (it equals the planet's distance in star sizes times the star's size). That route gives a different estimate, and its own uncertainty may cover this gap.",
                "With q = pl_ratdor: listed a = q × R* within 1%, and the orbit's eccentricity is 0 or not reported (q is the mid-transit distance, equal to a/R* only for a circular orbit; when eccentricity isn't reported the note assumes a circular orbit, an assumption, not a measurement). All four inputs need a usable uncertainty. Note when |a_listed ÷ a_Kepler − 1| ≤ 2 × √[(σ_q/q)² + (σ_R*/R*)² + (σ_M*/(3M*))² + (2σ_P/(3P))²]. All terms are fractional; errors treated as independent (q and R* can be correlated in a transit fit, so this note is provisional); the planet-mass term is negligible and not propagated; the listed orbit size's own error is left out because it is derived from q and R*."),
"B/B-transit-open": ("A planet's orbit size vs the orbit size from its orbit time and star mass.",
                     "This orbit size appears to come from the transit (it equals the planet's distance in star sizes times the star's size). That would explain where the number came from, but not why it disagrees with the period and star mass from the same paper: the gap is more than twice the combined uncertainty.",
                     "Detected by numbers only: listed a = pl_ratdor × R* within 1% and the orbit's eccentricity 0 or not reported (then a circular orbit is assumed; the paper itself isn't read). Gap above the B-transit allowance and ≥ 2 × the row's combined uncertainty. When the orbit is eccentric, the same numerical match is shown as 'numerical match only' and the card keeps its general title. One finding, not counted again under any other heading."),
"B/B-cat": ("A row whose values don't combine consistently.",
            "The row doesn't add up, and the star's size or mass in it comes from a star catalogue while the planet's values come from the paper, which may have used its own star values. That mix is shown as context; it may explain the gap, but nobody has checked.",
            "The card names the star's reference (e.g. TICv8). A different label doesn't prove the paper used different star values."),
"B/B-src": ("A row whose values don't combine consistently.",
            "The row doesn't add up, and the star's values in it cite a different paper than the planet's values. That mix is shown as context; it may explain the gap (the paper may still have used the same star values), but nobody has checked.",
            "Star reference ≠ planet reference."),
"B/B-dup": ("A row whose values don't combine consistently.",
            "NASA holds more than one row for this paper and planet. ExoDiff checks each row on its own and never mixes values across rows; the paper may report several solutions. Duplicate rows aren't independent results, and each is counted once.",
            "More than one archive row for the planet and paper."),
"B/B-close": ("A row whose values don't combine consistently.",
              "The gap is below ExoDiff's screening threshold (twice the combined uncertainty), so it isn't a finding, wherever the star's values came from.",
              STAT),
"B/B-look": ("A row whose values don't combine consistently.",
             "No explanation ExoDiff tests for matched, and the gap is more than twice the combined uncertainty. Worth checking the paper. A lead, not evidence that the paper or the archive is wrong.",
             STAT),

"card/public": ("A number on NASA's public catalog page vs the numbers in NASA's research archive for the same planet.",
                "Both are run by NASA, and the page usually shows one of the archive's values, rounded.\n\nIf the page shows **a number that appears in no archive row**, the difference is flagged for investigation. Either side may be out of date or use another source, and the page may show a derived value; ExoDiff doesn't decide which is right.",
                "The page's data feed (science.nasa.gov) vs the archive's PS table (one row per paper) and PSCompPars (NASA's combined table, which fills gaps from different papers and calculates some values)."),
"C/C-default": ("Catalog page vs archive.", "The page shows the value from NASA's selected parameter set (its 'default' paper for this planet, not necessarily the newest or most precise).", ""),
"C/C-composite": ("Catalog page vs archive.", "The page shows a value from PSCompPars, NASA's combined parameter table, which takes values from several papers and calculates some.", ""),
"C/C-other": ("Catalog page vs archive.", "The page's value matches another paper in the archive, while the archive's selected paper is a different one. The page and archive may update on different cycles.", ""),
"C/C-none": ("Catalog page vs archive.", "The page shows a number that none of NASA's archive rows for this planet has, nor its combined table. Either side may be out of date or use another source; ExoDiff doesn't decide which.", "Matched within the page's displayed digits, against every PS row and PSCompPars; the page's snapshot date is shown on the card."),
"C/C-survey": ("The distance in NASA's catalog data vs the archive's distance.", "Within 5% (ExoDiff's threshold) of each other. The catalog data may use a different distance source (not checked which); the page doesn't display distance.", "Same 5% measure as check E (larger ÷ smaller − 1)."),
"C/C-absent": ("Catalog page vs archive.", "One side has no value, so there's nothing to compare.", ""),
"C/C-estimate": ("The planet size on NASA's catalog page vs the archive.",
                 "NASA's page labels this size as an estimate: model-derived from the planet's mass rather than measured. Where no PS or PSCompPars value matches it (within the displayed digits), it's shown as a note rather than compared as a measurement.",
                 "Catalog text '(estimate)'; applied only when no archive or PSCompPars value matches."),

"card/eu": ("NASA's number vs exoplanet.eu's number for the same planet.",
            "Two independently maintained catalogues draw on overlapping published papers, so their numbers aren't independent measurements. They may pick different papers, conventions or derived values, so **a difference isn't automatically a copying error**. When the numbers clearly differ, exoplanet.eu's page tells us **which paper it used**, and we check whether NASA has it.",
            "exoplanet.eu CSV (CC BY 4.0) plus its planet pages for the cited paper; values compared in NASA's units. " + STAT),
"D/D-same": ("NASA vs exoplanet.eu.", "The same number within the digits shown (after unit conversion).", "Rounding of exoplanet.eu's digits + 0.3% for radius and mass, which are converted from Jupiter units (an ExoDiff convention)."),
"D/D-other-paper": ("NASA vs exoplanet.eu.", "exoplanet.eu shows the number from a different paper that NASA also holds. The catalogues selected different published solutions; the difference alone doesn't establish an error.", ""),
"D/D-within-errors": ("NASA vs exoplanet.eu.", "Different numbers, but their uncertainty ranges overlap: compatible under the stated uncertainties.", "Ranges widened by rounding and unit conversion."),
"D/D-disagree": ("NASA's number vs exoplanet.eu's number for the same planet.",
                 "More than twice the combined uncertainty apart, and no explanation ExoDiff tests for matched. When both cite the same single paper, the comparison is against NASA's row from that paper, and a copying or interpretation difference is worth checking. When exoplanet.eu lists several papers, ExoDiff doesn't say which one the number came from.",
                 STAT + " Mass is compared with NASA's true-mass column only; radius and mass use NASA's Jupiter-unit copy when the row has one."),
"D/D-newer-paper": ("NASA's number vs exoplanet.eu's number for the same planet.",
                    "exoplanet.eu cites a paper newer than any in NASA's archive for this planet, and the numbers differ by more than twice the combined uncertainty. NASA's archive may not yet include that result. Newer isn't automatically more correct.",
                    "The newest paper exoplanet.eu cites for this value is newer than NASA's newest row for the planet, and NASA's archive holds none of the papers cited; preprint status not checked. Radius and mass are compared using NASA's Jupiter-unit copy when the row has one. " + STAT),
"D/D-eu-paper": ("NASA vs exoplanet.eu.", "exoplanet.eu used a paper NASA's archive doesn't hold for this planet, and it isn't newer than NASA's. A source difference, not by itself a measurement contradiction.", ""),
"D/D-other-row": ("NASA vs exoplanet.eu.", "exoplanet.eu's number fits within the uncertainty of another row NASA holds (another paper, or another solution in the same paper).", "Used only when exoplanet.eu names no paper or names exactly that row's paper."),
"D/D-close": ("NASA vs exoplanet.eu.", "The ranges don't quite overlap, but the gap is below ExoDiff's threshold of twice the combined uncertainty.", STAT),
"D/D-letters": ("NASA vs exoplanet.eu.", "exoplanet.eu's numbers for this planet match NASA's for another planet around the same star: the two catalogues may give the planets different letters (b, c, d...). A disagreement about identity between the sources, so it's one finding per planet.", "Two routes, both ExoDiff's matching windows: (1) the whole planet: exoplanet.eu's orbit time is within 1% of a sibling planet's NASA value and more than 5% from its own, so every value except distance counts (21 of 22 planets in this snapshot); (2) one value within 1% of a sibling's for that field (1 planet: KMT-2024-BLG-0404L b, mass). Both routes apply whatever the size of the gap, on purpose: they concern which planet is meant, not how far apart the numbers are. A possible mismatch, not a confirmed letter swap; coincidental matches are possible."),
"D/D-limit": ("NASA vs exoplanet.eu.", "One side gives a limit ('at most' or 'at least') rather than a measurement, and the other side's value, with its range, is on the allowed side of it. Compatible, so shown as a note. Limits pointing in opposite directions can still conflict, and those stay findings.", "Upper limit L: compatible if the other's lower edge ≤ L. Lower limit: if the other's upper edge ≥ L. exoplanet.eu writes an upper limit as <field>_error_min equal to the value and <field>_error_max 0 or empty."),
"D/D-catalogue-distance": ("NASA's distance vs exoplanet.eu's.", "NASA's distance comes from a star catalogue rather than a paper, and the two catalogues may use different distance sources or methods. Not shown here; check E compares the star's distance with Gaia directly.", "An internal label only; it never appears on a page."),
"D/D-no-errors": ("NASA vs exoplanet.eu.", "At least one side gives no usable uncertainty, so ExoDiff can't judge how much the gap matters. Shown as a note only when they are far apart.", "Note shown when the values differ by more than 10% of NASA's value; for orbit stretch (eccentricity, 0 to 1), when they differ by more than 0.1 in absolute terms. ExoDiff's thresholds."),
"D/D-theoretical": ("NASA vs exoplanet.eu.", "exoplanet.eu labels its number theoretical (its own classification, covering various model methods), so it's left out of this measurement-to-measurement check.", ""),
"D/D-absent": ("NASA vs exoplanet.eu.", "One catalogue doesn't list this value.", ""),

"card/gaia": ("NASA's distance to the star vs the distance from Gaia, a European space telescope that maps over a billion stars.",
              "Most of NASA's distances (95%) come from a star catalogue built on Gaia's 2018 data; Gaia has since published updated distances.\n\nWhen the two distances are **5% or more apart and their uncertainty ranges don't overlap**, it is flagged for investigation: **NASA's value may predate the update**. When Gaia's own quality flags warn about the star, it is a note.",
              "TICv8 uses Bailer-Jones et al. (2018) distances from Gaia DR2 where available. Gaia DR3 contains the EDR3 astrometry and photometry plus new products; our distances are Bailer-Jones et al. (2021) geometric distances, posterior estimates from EDR3 parallaxes with a prior. Joined on NASA's own gaia_dr3_id. apart = larger ÷ smaller − 1."),
"E/E-same": ("NASA's distance vs Gaia's.", "The uncertainty ranges overlap: compatible.", ""),
"E/E-small": ("NASA's distance vs Gaia's.", "Less than 5% apart (ExoDiff's threshold).", ""),
"E/E-differs": ("NASA's distance to the star vs Gaia's updated distance.",
                "The uncertainty ranges don't overlap, the distances are 5% or more apart, and the star passed ExoDiff's Gaia-quality screens. NASA's distance source is named on the card (nearly always TICv8, built on Gaia's 2018 data), so NASA's value may predate Gaia's update; that is plausible, not proven for any one star, and a paper's own distance or method could also explain a gap. One finding on each planet of the star (several planets can share one star).",
                "apart = larger ÷ smaller − 1 ≥ 5%."),
"E/E-no-errors": ("NASA's distance vs Gaia's.", "NASA gives no uncertainty for its distance, so the gap can't be judged. A separate 'uncertainty unavailable' status.", ""),
"E/E-quality": ("NASA's distance to the star vs Gaia's.",
                "They differ, but Gaia's own quality flags warrant caution for this star (one possible cause is a close companion star), or the Gaia ID may point to a different source.",
                "Flags: RUWE > 1.4 (Gaia's documented caution indicator), and three ExoDiff screens: parallax ÷ its uncertainty < 5, excess-noise significance > 20 (deliberately strict; Gaia calls > 2 significant and advises choosing a cutoff per use), Gaia G brightness differs from NASA's Gaia G (sy_gaiamag) by > 1 magnitude (same band, but NASA's value may come from an earlier Gaia release). Screening indicators, not proof; passing them doesn't certify the match either."),

"F": ("Two places on the same NASA catalog page: the summary sentence and the facts box.",
      "The two can give different numbers. Most differences come from the sentence using a published solution held in NASA's archive (not the one the facts box shows), or a calculated orbit size; in some the facts box says 'Unknown', and a few have no identified cause. Papers are named when known. **Always a note**: this check is about the page's own consistency; whether the page matches the archive is the catalog check.",
      "Hover a note for its likely reason. Read from the catalog's data feed, which holds the page's sentence and facts box (identical on all 6,451 pages read on 2026-10-22)."),

"card/massKind": ("What kind of mass a number is.",
                  "Masses come three ways: a mass (from the star's wobble or timing changes, plus the orbit's tilt, which a transit can give), a minimum mass (wobble only, tilt unknown; the true mass is at least as large), or an estimate from the planet's size using a model. A label, not a disagreement.",
                  "NASA's PS column pl_bmassprov: Mass, Msini or Msin(i)/sin(i). Masses estimated from size with a model appear in NASA's combined table (PSCompPars), marked as calculated."),

"pattern/impossible": ("", "Outside the allowed range as stored (a negative size, uncertainty signs that don't follow the table convention, a value outside what the field allows).", ""),
"pattern/letters": ("", "Possible planet-letter or identity mismatch: exoplanet.eu's number matches another planet around the same star.", ""),
"pattern/system": ("", "Several planets around one star, from one paper, are off by the same percentage. That may point to a shared input or conversion.", ""),
"pattern/units": ("", "The two numbers differ by close to a unit ratio (Jupiter vs Earth: ×11.2 in size, ×318 in mass; years vs days: ×365). Consistent with a unit mix-up, worth checking.", "'Close to' = within 2% (ExoDiff's window)."),
"pattern/tenfold": ("", "The two numbers differ by close to ×10, ×100 or ×1000. Consistent with a decimal-place or unit-scaling issue, or a normal conversion between definitions.", "Within 2%."),
"pattern/double": ("", "One number is close to twice the other. A factor-of-two pattern worth checking.", "Within 2%."),
"pattern/timing": ("", "Orbit times that differ by less than 0.1% but by more than their tiny uncertainties. Different reference dates, data spans or models can produce this; check whether both refer to the same fitted model and date.", "0.1% is ExoDiff's threshold."),
"pattern/unit-copies": ("", "NASA's Earth-unit and Jupiter-unit copies don't convert into each other (same finding as check A5, not counted twice).", ""),
"pattern/catalog": ("", "NASA's catalog page showed a number no archive row has when ExoDiff copied it (snapshot date on the page).", ""),
"pattern/paper": ("", "Five or more open findings of this check come from rows citing the same paper (five is ExoDiff's heuristic).", "Counts open check-B findings per cited paper, across planets."),
"pattern/other": ("", "No simple pattern fits. That doesn't make it less interesting; it just has no recognised signature.", ""),

"about/intro": ("", "ExoDiff checks public exoplanet data for **inconsistencies**. It compares measurements within research archive records, across NASA's archive and public catalogue pages, against exoplanet.eu, and with updated stellar distances from Gaia.\n\nIt identifies **discrepancies worth investigating**, shows the evidence behind them, and tests possible explanations. **A finding is not proof of an error**, and ExoDiff **does not decide which published value is correct**.\n\nExoDiff focuses on automated consistency checks across catalogue records and public pages, linking discrepancies back to their sources rather than selecting a single value as correct.", ""),
"method/intro": ("", "ExoDiff runs **six checks every day** against public exoplanet data. Each check uses its own evidence and rules. The results are screening tools: **a discrepancy is a reason to investigate, not proof that a published value is wrong**.\n\nThe checks give three kinds of evidence: a value invalid as stored, a row that doesn't add up under a stated formula, and a value that differs from another source. None of them says which published value is correct.", ""),
"about/lead": ("", "Two values count as different when they are **more than 2 error bars apart**. An error bar is the ± range a paper gives for its value; ExoDiff combines the two values' ranges and allows for rounding. This applies to the row check and the exoplanet.eu check. The Gaia check instead asks for ranges that don't overlap and a gap of at least 5%, and the catalog checks compare the numbers shown. These are ExoDiff's screening rules, **not formal verdicts**.\n\nA difference becomes **a note rather than a finding** when it falls below the threshold, can't be judged reliably, involves a limit or a value labelled as an estimate, or matches an explanation ExoDiff treats as innocent: a unit convention, another paper NASA also holds, or a source flagging its own value. These may explain a difference but are not confirmed. Some patterns stay findings by design: exoplanet.eu citing a newer paper NASA doesn't have, and a possible mix-up of planet letters; a star value from a catalogue or another paper is shown as context, not as an explanation.\n\nAnything left is classified as a finding: **worth checking, not a proven error**.", STAT),
}

NEW["card/values"] = ("Each value in an archive row on its own, and its stored uncertainty.",
                      "Sizes, masses, densities, orbit times, orbit sizes and distances **can't be zero or negative**; an orbit's stretch "
                      "must be at least 0 and less than 1; uncertainties must follow the archive's sign convention; and a value stored in "
                      "both Earth and Jupiter units **should convert consistently** between the two. A star's distance should also "
                      "**match its parallax** (the tiny yearly shift in its position that sets its distance).", "Check A: rules A1-A8.")
NEW["card/rows"] = ("Each archive row against itself: values that simple physics links together.",
                    "A planet's size follows from its size relative to the star and the star's size; its density from its mass and size; "
                    "its orbit size from its orbit time and the star's mass; and, for a circular orbit, its distance counted in star sizes "
                    "from its orbit size and the star's size. Each row is tested **with its own values and uncertainties**.",
                    "Check B: the four identities below. " + STAT)

LABELS = {
    "A/A1": "value must be positive", "A/A2": "orbit stretch outside 0-1", "A/A3": "uncertainty sign", "A/A4": "limit with a ± range",
    "A/A5": "Earth and Jupiter copies differ", "A/A5m": "copies: average vs equator sizes", "A/A5r": "copies: rounded",
    "A/A7": "one paper, several rows", "A/A8": "distance doesn't match the parallax",
    "A/A8n": "distance doesn't match the parallax (NASA has a note)",
    "B/B-look": "row doesn't add up", "B/B-transit-open": "orbit size from the transit doesn't fit",
    "B/B-cat": "row doesn't add up (star value from a catalogue)", "B/B-src": "row doesn't add up (star value from another paper)",
    "B/B-doc": "row: NASA has a note", "B/B-meanR": "row: average vs equator sizes", "B/B-lit": "row: orbit size from older papers",
    "B/B-transit": "row: orbit size from the transit", "B/B-dup": "row: several rows for the paper",
    "B/B-close": "row: below the threshold",
    "C/C-none": "catalog page and archive differ", "C/C-other": "catalog page shows another paper's value",
    "C/C-survey": "catalog distance from another survey", "C/C-estimate": "catalog size is an estimate",
    "D/D-disagree": "exoplanet.eu disagrees", "D/D-newer-paper": "exoplanet.eu cites a newer paper",
    "D/D-letters": "exoplanet.eu may use another letter", "D/D-eu-paper": "exoplanet.eu uses another paper",
    "D/D-other-row": "exoplanet.eu matches another row", "D/D-close": "exoplanet.eu: below the threshold",
    "D/D-limit": "exoplanet.eu: limit compatible", "D/D-no-errors": "exoplanet.eu: can't be judged",
    "D/D-theoretical": "exoplanet.eu value theoretical",
    "E/E-differs": "Gaia distance differs", "E/E-quality": "Gaia distance (flagged by Gaia)",
    "F": "catalog page disagrees with itself", "card/massKind": "kind of mass",
}


def text(key: str) -> dict:
    compare, means, details = NEW[key]
    return {"compare": compare, "means": means, "details": details}


def plain(text: str) -> str:
    return text.replace("**", "")


def means(key: str) -> str:
    return plain(NEW[key][1])


def lead_key(lead: dict) -> str:
    kind, rule, bucket = lead["kind"], lead.get("rule"), lead.get("bucket")
    if kind == "A":
        return f"A/{rule}"
    if kind == "B":
        return "B/B-transit-open" if bucket == "B-look" and lead.get("transit_fit") else f"B/{bucket}"
    if kind == "C":
        return "card/massKind" if rule == "label" else f"C/{bucket}"
    if kind in ("D", "E"):
        return f"{kind}/{bucket}"
    return "F"


def export() -> dict:
    return {"texts": {k: text(k) for k in NEW}, "labels": LABELS, "statistic": STAT}
