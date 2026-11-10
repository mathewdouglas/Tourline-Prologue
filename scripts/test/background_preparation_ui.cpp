// Completion must wait for menus and eight visible seconds; no percentage guesses.
#include "../../launcher/background_preparation_ui.h"
#include <cassert>
#include <cstdio>
using namespace background_preparation_ui;
int main() {
    Notice state;
    assert(state.update(Work::Preparing,false,true,100)==View::Preparing);
    assert(state.update(Work::Paused,true,true,200)==View::Paused);
    assert(state.update(Work::Complete,true,true,300)==View::Hidden);
    assert(state.update(Work::Complete,true,true,30000)==View::Hidden);
    assert(state.update(Work::Complete,false,false,40000)==View::Hidden);
    assert(state.update(Work::Complete,false,true,50000)==View::CompleteNotice);
    assert(state.update(Work::Complete,false,true,53999)==View::CompleteNotice);
    assert(state.update(Work::Complete,false,false,54000)==View::Hidden);
    assert(state.update(Work::Complete,false,true,90000)==View::CompleteNotice);
    assert(state.update(Work::Complete,false,true,93999)==View::CompleteNotice);
    assert(state.update(Work::Complete,false,true,94000)==View::CompleteNotice);
    assert(state.update(Work::Complete,false,true,94001)==View::Ready);
    assert(state.update(Work::Complete,true,true,95000)==View::Hidden);
    assert(state.update(Work::Complete,false,true,96000)==View::Ready);
    assert(state.update(Work::Incomplete,true,true,97000)==View::Hidden);
    assert(state.update(Work::Incomplete,false,true,98000)==View::Incomplete);
    assert(state.update(Work::Preparing,false,false,99000)==View::Hidden);
    puts("Menu deferral, focus loss, eight visible seconds, ready persistence, pause and failure policy passed");
}
