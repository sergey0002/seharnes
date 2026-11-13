<?php

declare(strict_types=1);

namespace Tests\Support\Step;

use Tests\Support\AcceptanceTester;
use Tests\Support\Page\SigninPage;
use Tests\Support\Page\SignupPage;

/**
 * Обязательные поля modern signup/signin (CT-2591).
 * Селекторы только в Page.
 */
final class AuthRequiredFieldsSteps
{
    private AcceptanceTester $I;
    private SigninPage $signin;
    private SignupPage $signup;

    public function __construct(AcceptanceTester $I)
    {
        $this->I = $I;
        $this->signin = new SigninPage($I);
        $this->signup = new SignupPage($I);
    }

    public function signin(): SigninPage
    {
        return $this->signin;
    }

    public function signup(): SignupPage
    {
        return $this->signup;
    }

    public function assertSignupRequiredMarkers(): void
    {
        $this->signup->open();
        $this->signup->seeSignupFormContract();
        $this->signup->seeRequiredStars();
        $this->signup->seeOptionalFieldsHaveNoStar();
        $this->signup->seeVueNotHtml5Required();
    }

    public function assertSigninRequiredMarkers(): void
    {
        $this->signin->open();
        $this->signin->seeLoginFormContract();
        $this->signin->seeRequiredStars();
        $this->signin->seeVueNotHtml5Required();
    }

    public function assertSignupSubmitBlocked(): void
    {
        $this->signup->open();
        $this->signup->touchEmptyFieldsAndSeeVueErrors();
    }

    public function assertSigninSubmitBlocked(): void
    {
        $this->signin->open();
        $this->signin->seeEmptySubmitBlocked();
    }
}
